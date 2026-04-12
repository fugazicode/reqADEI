/**
 * KV namespace binding required in wrangler.toml: BOT_STATUS
 *
 * KV keys used:
 *   bot_last_seen      — Unix ms timestamp of last heartbeat (string)
 *   maintenance_mode   — "1" = on, "0" or absent = off
 *   down_message       — custom text to send users when down (optional)
 *   down_chat_ids      — JSON array of chat IDs that received a down message
 *
 * Environment variables (set via wrangler secret put):
 *   BOT_TOKEN                  — Telegram bot token
 *   WORKER_SECRET              — shared secret for /heartbeat, /maintenance, /recovery-queue
 *   TELEGRAM_WEBHOOK_SECRET    — validated on every incoming Telegram update
 *   LOCAL_BOT_URL              — Cloudflare Tunnel URL of local bot (no trailing slash)
 */

const HEARTBEAT_TIMEOUT_MS = 90_000;

const DEFAULT_DOWN_MESSAGE =
  "We are currently down for maintenance. We will be back as soon as possible.";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const method = request.method;

    if (method === "POST" && url.pathname === "/heartbeat") {
      return handleHeartbeat(request, env);
    }

    if (method === "POST" && url.pathname === "/maintenance/on") {
      return handleMaintenance(request, env, true);
    }

    if (method === "POST" && url.pathname === "/maintenance/off") {
      return handleMaintenance(request, env, false);
    }

    if (method === "GET" && url.pathname === "/recovery-queue") {
      return handleRecoveryQueue(request, env);
    }

    if (method === "POST" && url.pathname === "/webhook") {
      return handleTelegramWebhook(request, env, ctx);
    }

    return new Response("Not found", { status: 404 });
  },
};

// ── Heartbeat ──────────────────────────────────────────────────────────────

async function handleHeartbeat(request, env) {
  if (!validateWorkerSecret(request, env)) {
    return new Response("Unauthorized", { status: 401 });
  }
  await env.BOT_STATUS.put("bot_last_seen", String(Date.now()));
  return new Response("OK", { status: 200 });
}

// ── Maintenance mode ───────────────────────────────────────────────────────

async function handleMaintenance(request, env, enabled) {
  if (!validateWorkerSecret(request, env)) {
    return new Response("Unauthorized", { status: 401 });
  }
  await env.BOT_STATUS.put("maintenance_mode", enabled ? "1" : "0");
  return new Response(enabled ? "Maintenance ON" : "Maintenance OFF", { status: 200 });
}

// ── Recovery queue ─────────────────────────────────────────────────────────

async function handleRecoveryQueue(request, env) {
  if (!validateWorkerSecret(request, env)) {
    return new Response("Unauthorized", { status: 401 });
  }
  const raw = await env.BOT_STATUS.get("down_chat_ids");
  // Clear the list atomically before returning so concurrent bot startups
  // don't double-send recovery messages.
  await env.BOT_STATUS.delete("down_chat_ids");
  const ids = raw ? JSON.parse(raw) : [];
  return new Response(JSON.stringify(ids), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

// ── Telegram webhook ───────────────────────────────────────────────────────

async function handleTelegramWebhook(request, env, ctx) {
  const telegramSecret = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
  if (telegramSecret !== env.TELEGRAM_WEBHOOK_SECRET) {
    return new Response("Unauthorized", { status: 401 });
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return new Response("Bad request", { status: 400 });
  }

  // Always return 200 to Telegram immediately.
  // All work (forwarding or replying) runs in ctx.waitUntil so Cloudflare
  // does not terminate the Worker before the async work completes.
  ctx.waitUntil(processUpdate(body, env));
  return new Response("OK", { status: 200 });
}

async function processUpdate(body, env) {
  const maintenanceMode = await env.BOT_STATUS.get("maintenance_mode");
  if (maintenanceMode === "1") {
    await handleDownUpdate(body, env, "maintenance");
    return;
  }

  const lastSeenStr = await env.BOT_STATUS.get("bot_last_seen");
  if (!lastSeenStr) {
    await handleDownUpdate(body, env, "no_heartbeat");
    return;
  }

  const elapsed = Date.now() - parseInt(lastSeenStr, 10);
  if (elapsed > HEARTBEAT_TIMEOUT_MS) {
    await handleDownUpdate(body, env, "heartbeat_timeout");
    return;
  }

  // Bot is healthy — forward raw update to local bot via tunnel.
  try {
    await fetch(`${env.LOCAL_BOT_URL}/webhook`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // Re-send the Telegram secret so aiogram's SimpleRequestHandler
        // validates it and doesn't reject the forwarded update.
        "X-Telegram-Bot-Api-Secret-Token": env.TELEGRAM_WEBHOOK_SECRET,
      },
      body: JSON.stringify(body),
    });
  } catch {
    // Tunnel is unreachable despite a recent heartbeat (e.g. tunnel crashed
    // between heartbeats). Fall back to down message rather than silent drop.
    await handleDownUpdate(body, env, "tunnel_unreachable");
  }
}

// ── Down handling ──────────────────────────────────────────────────────────

async function handleDownUpdate(body, env, reason) {
  const chatId = extractChatId(body);
  if (!chatId) return;

  const downMessage =
    (await env.BOT_STATUS.get("down_message")) || DEFAULT_DOWN_MESSAGE;

  // Send down message to user.
  await fetch(
    `https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text: downMessage }),
    }
  );

  // If this was triggered by a callback_query, answer it to clear the
  // loading spinner on the button — without this the button spins indefinitely.
  if (body.callback_query?.id) {
    await fetch(
      `https://api.telegram.org/bot${env.BOT_TOKEN}/answerCallbackQuery`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ callback_query_id: body.callback_query.id }),
      }
    );
  }

  // Record this chat_id for the recovery notification queue.
  // Read-modify-write is acceptable here — concurrent writes are extremely
  // unlikely during a downtime event, and duplicates are deduplicated below.
  const raw = await env.BOT_STATUS.get("down_chat_ids");
  const ids = raw ? JSON.parse(raw) : [];
  if (!ids.includes(chatId)) {
    ids.push(chatId);
    await env.BOT_STATUS.put("down_chat_ids", JSON.stringify(ids));
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────

function validateWorkerSecret(request, env) {
  return request.headers.get("X-Worker-Secret") === env.WORKER_SECRET;
}

function extractChatId(body) {
  // Cover the update types this bot actually receives.
  return (
    body?.message?.chat?.id ??
    body?.callback_query?.message?.chat?.id ??
    body?.edited_message?.chat?.id ??
    null
  );
}

from __future__ import annotations

import asyncio
import logging

import aiohttp
from aiogram import Bot

LOGGER = logging.getLogger(__name__)


async def heartbeat_loop(
    worker_url: str,
    secret: str,
    interval: int = 30,
) -> None:
    """Sends a POST to /heartbeat every `interval` seconds.

    Sends the first ping before the first sleep so the Worker knows the bot is
    up within milliseconds of this task being created.
    """
    headers = {"X-Worker-Secret": secret}
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.post(
                    f"{worker_url}/heartbeat",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        LOGGER.warning(
                            "Heartbeat endpoint rejected ping with status %d", resp.status
                        )
            except Exception as exc:
                LOGGER.warning("Heartbeat ping failed: %s", exc)

            await asyncio.sleep(interval)


async def notify_recovery(
    worker_url: str,
    secret: str,
    bot: Bot,
) -> None:
    """Fetches the list of chat IDs that received a down message from the Worker,
    sends each a 'we're back' message, and the Worker clears the list atomically.

    Called once during on_startup before the heartbeat loop starts.
    Failures are logged and swallowed — recovery notification is best-effort.
    """
    headers = {"X-Worker-Secret": secret}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{worker_url}/recovery-queue",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    LOGGER.warning(
                        "Recovery queue endpoint returned %d — skipping recovery notifications",
                        resp.status,
                    )
                    return
                chat_ids: list[int] = await resp.json()
    except Exception as exc:
        LOGGER.warning("Failed to fetch recovery queue: %s", exc)
        return

    if not chat_ids:
        return

    LOGGER.info("Sending recovery notification to %d user(s)", len(chat_ids))
    for chat_id in chat_ids:
        try:
            await bot.send_message(
                chat_id,
                "✅ We're back online. Sorry for the interruption. Send /start to continue.",
            )
        except Exception as exc:
            LOGGER.warning(
                "Failed to send recovery message to chat_id=%s: %s", chat_id, exc
            )

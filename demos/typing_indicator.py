"""
Telegram Bot — Animated Typing Indicator (demo)
-----------------------------------------------
Displays randomly selected messages with a typewriter animation
while your bot is processing. Uses only the `requests` library.

Animation note: each visible step is a Telegram ``editMessageText`` call, so
effective timing is ``max(RTT, local pacing)``. Pauses follow **research-style**
presets: ``snappy`` (~50 ms/char) vs ``natural`` (~260 ms/char). Each step scales
with **word or chunk length**, plus jitter, ``STEP_PACE_SCALE``, and a small
punctuation bonus. Tune ``PACING_PRESET``, ``STEP_PACE_SCALE``, ``ERASE_PACE_MULTIPLIER``,
and ``MIN_EDIT_INTERVAL_API`` (429 safety floor) as needed.

The default is **word-to-word** reveal (CLI-style status). Set
``TYPE_BY_WORDS`` to False for fixed-size character chunks instead.

Environment (.env at repo root, or cwd):
    BOT_TOKEN              — required for API calls
    TYPING_DEMO_CHAT_ID    — optional; used by __main__ if set
    ADMIN_TELEGRAM_ID      — fallback chat id for __main__ demo

Usage:
    pip install -r requirements.txt
    python demos/typing_indicator.py

    Or import and call `show_typing_indicator(chat_id, stop_event)` / `TypingIndicator`.
"""

from __future__ import annotations

import os
import random
import threading
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env from repository root when this file lives under demos/
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv()  # also respect cwd .env if present

# ─────────────────────────────────────────
#  CONFIG — from .env / environment
# ─────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ─────────────────────────────────────────
#  ROTATING MESSAGE POOL
#  Add / remove / customise freely
# ─────────────────────────────────────────
TYPING_MESSAGES = [
    "Thinking really hard",
    "Crunching the numbers",
    "Consulting the oracle",
    "Brewing something special",
    "Loading awesomeness",
    "Assembling the answer",
    "Doing the math",
    "Searching the archives",
    "Almost there",
    "Hang tight, working on it",
    "Generating brilliance",
    "Asking the AI overlords",
]

# ─────────────────────────────────────────
#  ANIMATION SETTINGS
# ─────────────────────────────────────────
# Word-to-word: one API edit per whole word (recommended). Character chunks if
# TYPE_BY_WORDS is False (chunk size = CHARS_PER_EDIT).
TYPE_BY_WORDS = True
CHARS_PER_EDIT = 4  # used when TYPE_BY_WORDS is False; minimum 1

CURSOR = "▌"  # shown at end of line while words are still being “typed”
HOLD_DURATION = 0.85  # seconds to show the finished line (no cursor)
BETWEEN_MESSAGES = 0.2  # pause before the next phrase

# Pacing preset: "snappy" (~50 ms/char) vs "natural" (slower, human-ish).
PACING_PRESET: str = "natural"
PACING_VARIANCE = 0.2  # multiplicative jitter ± this fraction (0 = none)
PUNCTUATION_BONUS_SEC = 0.08  # extra pause if step token ends in .,!?;:,
# Tiny pause after each type-in step only in "natural" (snappy keeps 0).
WORD_BOUNDARY_BONUS_NATURAL_SEC = 0.02
# 1.0 = erase as slow as type-in; below 1 erases faster; above 1 erases slower.
ERASE_PACE_MULTIPLIER = 1.0

# Multiplies every type-in/erase step pause (after bonuses). >1 = slower overall.
STEP_PACE_SCALE = 1.15

PAUSE_MIN_SEC = 0.02
PAUSE_MAX_SEC = 1.25  # cap long tokens so one step does not stall the UI

# Minimum time between completed edits (429 / flood control). Not the main feel.
MIN_EDIT_INTERVAL_API = 0.08

# Preset → base ms/char: "snappy" ≈ 50; "natural" ≈ 260. Pause uses STEP_PACE_SCALE,
# then clamp; then max(..., MIN_EDIT_INTERVAL_API). Erase uses ERASE_PACE_MULTIPLIER.


# ══════════════════════════════════════════
#  LOW-LEVEL TELEGRAM HELPERS
# ══════════════════════════════════════════


def _send_message(chat_id: int | str, text: str) -> dict:
    """Send a new message and return the full response dict."""
    resp = requests.post(
        f"{BASE_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    return resp.json()


def _sleep_interruptible(seconds: float, stop_event: threading.Event | None) -> bool:
    """Sleep up to ``seconds``; return True if ``stop_event`` was set."""
    if seconds <= 0:
        return bool(stop_event and stop_event.is_set())
    if stop_event is None:
        time.sleep(seconds)
        return False
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if stop_event.is_set():
            return True
        time.sleep(min(0.2, end - time.monotonic()))
    return False


def _edit_message(
    chat_id: int | str,
    message_id: int,
    text: str,
    *,
    stop_event: threading.Event | None = None,
) -> bool:
    """
    Edit an existing message. Retries on 429 using ``retry_after``.
    Treats 'message is not modified' as success.
    """
    while True:
        if stop_event is not None and stop_event.is_set():
            return False
        resp = requests.post(
            f"{BASE_URL}/editMessageText",
            json={"chat_id": chat_id, "message_id": message_id, "text": text},
            timeout=10,
        )
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if data.get("ok"):
            return True
        desc = (data.get("description") or "").lower()
        if "not modified" in desc:
            return True
        if resp.status_code == 429:
            params = data.get("parameters") or {}
            try:
                retry_after = float(params.get("retry_after", 1.0))
            except (TypeError, ValueError):
                retry_after = 1.0
            retry_after = min(max(retry_after, 0.5), 30.0)
            if _sleep_interruptible(retry_after, stop_event):
                return False
            continue
        return False


def _base_ms_per_char() -> float:
    p = (PACING_PRESET or "snappy").strip().lower()
    if p == "natural":
        return 260.0
    return 50.0


def _wait_api_floor_since(last_edit_monotonic: float, stop_event: threading.Event) -> bool:
    """Ensure MIN_EDIT_INTERVAL_API since last edit completed. True if cancelled."""
    if MIN_EDIT_INTERVAL_API <= 0:
        return bool(stop_event.is_set())
    wait = MIN_EDIT_INTERVAL_API - (time.monotonic() - last_edit_monotonic)
    if wait > 0:
        return _sleep_interruptible(wait, stop_event)
    return False


def _token_ends_punct(token: str) -> bool:
    t = token.rstrip()
    return bool(t) and t[-1] in ".,!?;:"


def _step_token_type_in(prev_prefix: str, new_prefix: str, *, by_words: bool) -> str:
    if by_words:
        words = new_prefix.split()
        return words[-1] if words else ""
    if new_prefix.startswith(prev_prefix):
        return new_prefix[len(prev_prefix) :]
    return new_prefix


def _step_token_erase(longer: str, shorter: str, *, by_words: bool) -> str:
    if by_words:
        lw, sw = longer.split(), shorter.split()
        if len(lw) > len(sw):
            return lw[-1]
        return lw[-1] if lw else ""
    if longer.startswith(shorter):
        return longer[len(shorter) :]
    return ""


def _research_pause_sec(token: str, *, erase: bool) -> float:
    n = max(len(token), 1)
    ms = _base_ms_per_char()
    if PACING_VARIANCE > 0:
        jitter = 1.0 + random.uniform(-PACING_VARIANCE, PACING_VARIANCE)
        jitter = max(jitter, 0.15)
    else:
        jitter = 1.0
    sec = (ms / 1000.0) * n * jitter
    if _token_ends_punct(token):
        sec += PUNCTUATION_BONUS_SEC
    if not erase and (PACING_PRESET or "").strip().lower() == "natural":
        sec += WORD_BOUNDARY_BONUS_NATURAL_SEC
    if erase:
        sec *= ERASE_PACE_MULTIPLIER
    sec *= STEP_PACE_SCALE
    return max(PAUSE_MIN_SEC, min(PAUSE_MAX_SEC, sec))


def _sleep_pacing_after_edit(
    token: str,
    *,
    erase: bool,
    stop_event: threading.Event,
) -> bool:
    """Sleep max(research pause, API floor). True if stop_event interrupted."""
    pause = max(_research_pause_sec(token, erase=erase), MIN_EDIT_INTERVAL_API)
    return _sleep_interruptible(pause, stop_event)


def _typewriter_prefixes(phrase: str, *, by_words: bool, chars_per_edit: int) -> list[str]:
    """Monotonic prefixes for type-in (and reversed for erase)."""
    if by_words:
        words = phrase.split()
        if not words:
            return [phrase] if phrase else []
        return [" ".join(words[: k + 1]) for k in range(len(words))]

    step = max(1, chars_per_edit)
    if not phrase:
        return []
    out: list[str] = []
    pos = step
    while pos < len(phrase):
        out.append(phrase[:pos])
        pos += step
    out.append(phrase)
    return out


def _delete_message(chat_id: int | str, message_id: int) -> bool:
    """Delete a message. Returns True on success."""
    resp = requests.post(
        f"{BASE_URL}/deleteMessage",
        json={"chat_id": chat_id, "message_id": message_id},
        timeout=10,
    )
    return resp.json().get("ok", False)


def _send_chat_action(chat_id: int | str) -> None:
    """Send the native 'typing…' indicator in the chat header."""
    requests.post(
        f"{BASE_URL}/sendChatAction",
        json={"chat_id": chat_id, "action": "typing"},
        timeout=5,
    )


# ══════════════════════════════════════════
#  CORE ANIMATION LOOP
# ══════════════════════════════════════════


def _animation_loop(chat_id: int | str, stop_event: threading.Event) -> None:
    """
    Internal loop — runs on a background thread.
    Picks a random message, reveals it word-by-word (or by char chunks),
    holds on the finished line, then shortens word-by-word and clears.
    Stops when stop_event is set.
    """
    used_indices: list[int] = []  # avoid immediate repeats

    # ── send placeholder so we have a message_id to edit ──
    result = _send_message(chat_id, CURSOR)
    if not result.get("ok"):
        print(f"[TypingIndicator] Failed to send initial message: {result}")
        return

    message_id: int = result["result"]["message_id"]
    last_edit = time.monotonic()

    try:
        while not stop_event.is_set():
            # ── pick a non-repeating random message ──
            available = [i for i in range(len(TYPING_MESSAGES)) if i not in used_indices]
            if not available:
                used_indices.clear()
                available = list(range(len(TYPING_MESSAGES)))

            idx = random.choice(available)
            used_indices.append(idx)
            if len(used_indices) > max(1, len(TYPING_MESSAGES) // 2):
                used_indices.pop(0)

            phrase = TYPING_MESSAGES[idx]
            prefixes = _typewriter_prefixes(
                phrase, by_words=TYPE_BY_WORDS, chars_per_edit=CHARS_PER_EDIT
            )
            if not prefixes:
                time.sleep(BETWEEN_MESSAGES)
                continue

            # ── also keep native Telegram typing indicator alive ──
            _send_chat_action(chat_id)

            # ── WORD / CHUNK REVEAL (one edit per step, cursor at end of line) ──
            prev_prefix = ""
            for prefix in prefixes:
                if stop_event.is_set():
                    break
                if not prev_prefix and _wait_api_floor_since(last_edit, stop_event):
                    break
                token = _step_token_type_in(
                    prev_prefix, prefix, by_words=TYPE_BY_WORDS
                )
                partial = prefix + CURSOR
                _edit_message(chat_id, message_id, partial, stop_event=stop_event)
                last_edit = time.monotonic()
                if _sleep_pacing_after_edit(
                    token, erase=False, stop_event=stop_event
                ):
                    break
                prev_prefix = prefix

            if stop_event.is_set():
                break

            # ── hold finished line (no cursor — calm, status-line style) ──
            if _wait_api_floor_since(last_edit, stop_event):
                break
            _edit_message(chat_id, message_id, phrase, stop_event=stop_event)
            last_edit = time.monotonic()
            if _sleep_interruptible(HOLD_DURATION, stop_event):
                break

            if stop_event.is_set():
                break

            # ── shorten line word-by-word / chunk-by-chunk (plain text, no cursor) ──
            prev_line = phrase
            for prefix in reversed(prefixes[:-1]):
                if stop_event.is_set():
                    break
                tok = _step_token_erase(
                    prev_line, prefix, by_words=TYPE_BY_WORDS
                )
                _edit_message(chat_id, message_id, prefix, stop_event=stop_event)
                last_edit = time.monotonic()
                if _sleep_pacing_after_edit(tok, erase=True, stop_event=stop_event):
                    break
                prev_line = prefix

            if stop_event.is_set():
                break

            if _wait_api_floor_since(last_edit, stop_event):
                break
            final_tok = _step_token_erase(prev_line, "", by_words=TYPE_BY_WORDS)
            _edit_message(chat_id, message_id, CURSOR, stop_event=stop_event)
            last_edit = time.monotonic()
            if _sleep_pacing_after_edit(
                final_tok, erase=True, stop_event=stop_event
            ):
                break

            if _sleep_interruptible(BETWEEN_MESSAGES, stop_event):
                break

    finally:
        # always clean up the indicator message when done
        _delete_message(chat_id, message_id)


# ══════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════


class TypingIndicator:
    """
    Context-manager and manual-start/stop wrapper.

    ── As a context manager (recommended) ──────────────────
        with TypingIndicator(chat_id):
            result = do_heavy_work()
        bot.send_message(chat_id, result)

    ── Manual control ───────────────────────────────────────
        ti = TypingIndicator(chat_id)
        ti.start()
        ...
        ti.stop()
    """

    def __init__(self, chat_id: int | str):
        self.chat_id = chat_id
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> TypingIndicator:
        self._stop.clear()
        self._thread = threading.Thread(
            target=_animation_loop,
            args=(self.chat_id, self._stop),
            daemon=True,
            name="TypingIndicator",
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._thread and self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=5)

    # context-manager support
    def __enter__(self) -> TypingIndicator:
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()


def show_typing_indicator(
    chat_id: int | str,
    stop_event: threading.Event,
) -> None:
    """
    Thin wrapper for callers that manage their own threading.Event.

        stop = threading.Event()
        t = threading.Thread(target=show_typing_indicator, args=(chat_id, stop))
        t.start()
        # … do work …
        stop.set()
        t.join()
    """
    _animation_loop(chat_id, stop_event)


def _resolve_demo_chat_id() -> str | None:
    """Chat id for __main__: env TYPING_DEMO_CHAT_ID, then ADMIN_TELEGRAM_ID."""
    for key in ("TYPING_DEMO_CHAT_ID", "ADMIN_TELEGRAM_ID"):
        raw = os.getenv(key, "").strip()
        if raw:
            return raw
    return None


# ══════════════════════════════════════════
#  QUICK DEMO  (python demos/typing_indicator.py)
# ══════════════════════════════════════════
if __name__ == "__main__":
    import sys

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        sys.exit("Set BOT_TOKEN in .env (repo root) or environment.")

    chat_id = _resolve_demo_chat_id()
    if not chat_id:
        chat_id = input("Enter your chat_id to test: ").strip()
    if not chat_id:
        sys.exit("No chat_id provided. Set TYPING_DEMO_CHAT_ID or ADMIN_TELEGRAM_ID in .env.")

    print("Typing indicator running until you stop it (Ctrl+C or close the terminal).")

    try:
        with TypingIndicator(chat_id):
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped — indicator removed from chat.")

"""
Persistent analytics storage (SQLite via aiosqlite).

Schema
──────
sessions            — one row per bot conversation (telegram_user_id, times, outcome)
field_edits         — one row each time a field value changes (who changed, from/to, source)
fsm_transitions     — one row per state change (optional context JSON)
extraction_events   — ID extraction / validation outcomes per person
playwright_runs     — one row per portal automation attempt
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import aiosqlite

_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id    INTEGER NOT NULL,
    started_at          REAL    NOT NULL,
    consent_at          REAL,
    owner_upload_at     REAL,
    tenant_upload_at    REAL,
    first_review_at     REAL,
    submitted_at        REAL,
    completed_at        REAL,
    outcome             TEXT,        -- 'submitted' | 'abandoned' | 'error'
    error_message       TEXT,
    total_duration_s    REAL,
    field_edit_count    INTEGER DEFAULT 0,
    fsm_steps           INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS field_edits (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          INTEGER NOT NULL REFERENCES sessions(id),
    telegram_user_id    INTEGER NOT NULL,
    ts                  REAL    NOT NULL,
    field_path          TEXT    NOT NULL,
    old_value           TEXT,
    new_value           TEXT,
    source              TEXT    NOT NULL  -- 'ocr' | 'llm' | 'user_free_text' | 'user_picker'
);

CREATE TABLE IF NOT EXISTS fsm_transitions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          INTEGER NOT NULL REFERENCES sessions(id),
    telegram_user_id    INTEGER NOT NULL,
    ts                  REAL    NOT NULL,
    from_state          TEXT,
    to_state            TEXT,
    context             TEXT
);

CREATE TABLE IF NOT EXISTS extraction_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          INTEGER REFERENCES sessions(id),
    telegram_user_id    INTEGER NOT NULL,
    ts                  REAL    NOT NULL,
    person              TEXT    NOT NULL,
    image_count         INTEGER NOT NULL,
    raw_groq_response   TEXT,
    validation_error    TEXT,
    aadhaar_valid       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS playwright_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          INTEGER NOT NULL REFERENCES sessions(id),
    telegram_user_id    INTEGER NOT NULL,
    started_at          REAL    NOT NULL,
    finished_at         REAL,
    duration_s          REAL,
    outcome             TEXT,        -- 'success' | 'error'
    request_number      TEXT,
    error_message       TEXT,
    payload_snapshot    TEXT         -- JSON
);
"""


class AnalyticsStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_DDL)
        await self._db.commit()
        try:
            await self._db.execute("ALTER TABLE fsm_transitions ADD COLUMN context TEXT")
            await self._db.commit()
        except Exception:
            pass

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    # ── Sessions ─────────────────────────────────────────────────────────────

    async def open_session(self, telegram_user_id: int) -> int:
        """Insert a new session row and return its id."""
        assert self._db
        async with self._db.execute(
            "INSERT INTO sessions (telegram_user_id, started_at) VALUES (?, ?)",
            (telegram_user_id, time.time()),
        ) as cur:
            row_id = cur.lastrowid
        await self._db.commit()
        return row_id  # type: ignore[return-value]

    async def update_session(self, session_id: int, **kwargs: Any) -> None:
        """Update arbitrary columns on a session row."""
        assert self._db
        if not kwargs:
            return
        cols = ", ".join(f"{k} = ?" for k in kwargs)
        await self._db.execute(
            f"UPDATE sessions SET {cols} WHERE id = ?",
            (*kwargs.values(), session_id),
        )
        await self._db.commit()

    async def close_session(
        self,
        session_id: int,
        outcome: str,
        error_message: Optional[str] = None,
    ) -> None:
        now = time.time()
        assert self._db
        async with self._db.execute(
            "SELECT started_at FROM sessions WHERE id = ?", (session_id,)
        ) as cur:
            row = await cur.fetchone()
        started = row["started_at"] if row else now
        await self._db.execute(
            """UPDATE sessions SET
                completed_at = ?,
                outcome = ?,
                error_message = ?,
                total_duration_s = ?
            WHERE id = ?""",
            (now, outcome, error_message, now - started, session_id),
        )
        await self._db.commit()

    # ── Field edits ───────────────────────────────────────────────────────────

    async def log_field_edit(
        self,
        session_id: int,
        telegram_user_id: int,
        field_path: str,
        old_value: Any,
        new_value: Any,
        source: str,
    ) -> None:
        """
        source — one of: 'ocr', 'llm', 'user_free_text', 'user_picker'
        """
        assert self._db
        await self._db.execute(
            """INSERT INTO field_edits
               (session_id, telegram_user_id, ts, field_path, old_value, new_value, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                telegram_user_id,
                time.time(),
                field_path,
                str(old_value) if old_value is not None else None,
                str(new_value) if new_value is not None else None,
                source,
            ),
        )
        await self._db.execute(
            "UPDATE sessions SET field_edit_count = field_edit_count + 1 WHERE id = ?",
            (session_id,),
        )
        await self._db.commit()

    # ── FSM transitions ───────────────────────────────────────────────────────

    async def log_fsm_transition(
        self,
        session_id: int,
        telegram_user_id: int,
        from_state: Optional[str],
        to_state: Optional[str],
        context: Optional[dict] = None,
    ) -> None:
        assert self._db
        await self._db.execute(
            """INSERT INTO fsm_transitions
               (session_id, telegram_user_id, ts, from_state, to_state, context)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                telegram_user_id,
                time.time(),
                from_state,
                to_state,
                json.dumps(context) if context else None,
            ),
        )
        await self._db.execute(
            "UPDATE sessions SET fsm_steps = fsm_steps + 1 WHERE id = ?",
            (session_id,),
        )
        await self._db.commit()

    async def log_extraction_event(
        self,
        session_id: Optional[int],
        telegram_user_id: int,
        person: str,
        image_count: int,
        raw_groq_response: Optional[dict],
        validation_error: Optional[str],
        aadhaar_valid: bool,
    ) -> None:
        assert self._db
        await self._db.execute(
            """INSERT INTO extraction_events
               (session_id, telegram_user_id, ts, person, image_count,
                raw_groq_response, validation_error, aadhaar_valid)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                telegram_user_id,
                time.time(),
                person,
                image_count,
                json.dumps(raw_groq_response) if raw_groq_response else None,
                validation_error,
                1 if aadhaar_valid else 0,
            ),
        )
        await self._db.commit()

    # ── Playwright runs ───────────────────────────────────────────────────────

    async def log_playwright_start(self, session_id: int, telegram_user_id: int) -> int:
        assert self._db
        async with self._db.execute(
            """INSERT INTO playwright_runs (session_id, telegram_user_id, started_at, outcome)
               VALUES (?, ?, ?, 'running')""",
            (session_id, telegram_user_id, time.time()),
        ) as cur:
            row_id = cur.lastrowid
        await self._db.commit()
        return row_id  # type: ignore[return-value]

    async def log_playwright_finish(
        self,
        run_id: int,
        outcome: str,
        request_number: Optional[str] = None,
        error_message: Optional[str] = None,
        payload_snapshot: Optional[dict] = None,
    ) -> None:
        now = time.time()
        assert self._db
        async with self._db.execute(
            "SELECT started_at FROM playwright_runs WHERE id = ?", (run_id,)
        ) as cur:
            row = await cur.fetchone()
        started = row["started_at"] if row else now
        await self._db.execute(
            """UPDATE playwright_runs SET
                finished_at = ?,
                duration_s = ?,
                outcome = ?,
                request_number = ?,
                error_message = ?,
                payload_snapshot = ?
            WHERE id = ?""",
            (
                now,
                now - started,
                outcome,
                request_number,
                error_message,
                json.dumps(payload_snapshot) if payload_snapshot else None,
                run_id,
            ),
        )
        await self._db.commit()

    # ── Queries (for debugging / optimisation) ────────────────────────────────

    async def get_session_summary(self, session_id: int) -> Optional[dict]:
        assert self._db
        async with self._db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def get_field_edits(self, session_id: int) -> list[dict]:
        assert self._db
        async with self._db.execute(
            "SELECT * FROM field_edits WHERE session_id = ? ORDER BY ts", (session_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

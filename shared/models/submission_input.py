"""Contract between conversation-layer collection and portal automation.

Anything that enqueues work for `SubmissionWorker` should assemble this structure.
`FormPayload` field names and shape must stay aligned with `FormFiller` DOM mapping.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.models.form_payload import FormPayload


@dataclass
class SubmissionInput:
    """Payload and binary inputs required for one Playwright portal run."""

    telegram_user_id: int
    payload: FormPayload
    image_bytes: bytes
    analytics_session_id: int | None = None

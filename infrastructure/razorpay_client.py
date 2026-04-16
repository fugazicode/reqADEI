from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

LOGGER = logging.getLogger(__name__)


class RazorpayError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


class RazorpayClient:
    def __init__(self, key_id: str, key_secret: str, *, base_url: str = "https://api.razorpay.com/v1") -> None:
        self._base_url = base_url.rstrip("/")
        self._session = aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(key_id, key_secret),
            headers={"Accept": "application/json"},
        )

    async def close(self) -> None:
        if not self._session.closed:
            await self._session.close()

    async def create_payment_link(
        self,
        *,
        amount_paise: int,
        currency: str,
        reference_id: str,
        description: str,
        expire_by: int,
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "amount": amount_paise,
            "currency": currency,
            "reference_id": reference_id,
            "description": description,
            "expire_by": expire_by,
            "accept_partial": False,
            "notes": notes or {},
        }
        async with self._session.post(f"{self._base_url}/payment_links", json=payload) as resp:
            raw = await resp.text()
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {"raw": raw}
            if resp.status >= 400:
                raise RazorpayError(
                    f"Razorpay create_payment_link failed with status {resp.status}",
                    status=resp.status,
                    payload=data,
                )
            if not isinstance(data, dict):
                raise RazorpayError("Razorpay create_payment_link returned unexpected payload", payload=data)
            return data

    async def get_payment_link(self, link_id: str) -> dict[str, Any]:
        async with self._session.get(f"{self._base_url}/payment_links/{link_id}") as resp:
            raw = await resp.text()
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {"raw": raw}
            if resp.status >= 400:
                raise RazorpayError(
                    f"Razorpay get_payment_link failed with status {resp.status}",
                    status=resp.status,
                    payload=data,
                )
            if not isinstance(data, dict):
                raise RazorpayError("Razorpay get_payment_link returned unexpected payload", payload=data)
            return data

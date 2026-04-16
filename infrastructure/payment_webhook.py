from __future__ import annotations

import hashlib
import hmac
import json
import logging

from aiohttp import web

from infrastructure.payment_service import PaymentService

LOGGER = logging.getLogger(__name__)


class PaymentWebhookServer:
    def __init__(
        self,
        payment_service: PaymentService,
        *,
        secret: str,
        host: str,
        port: int,
        path: str,
    ) -> None:
        self._payment_service = payment_service
        self._secret = secret
        self._host = host
        self._port = port
        self._path = path
        self._app = web.Application()
        self._app.router.add_post(self._path, self._handle_webhook)
        self._runner = web.AppRunner(self._app)
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        LOGGER.info("Payment webhook server listening on %s:%s%s", self._host, self._port, self._path)

    async def stop(self) -> None:
        await self._runner.cleanup()

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        body = await request.read()
        signature = request.headers.get("X-Razorpay-Signature", "")
        if not signature or not _verify_signature(body, signature, self._secret):
            LOGGER.warning("Rejected webhook: invalid signature")
            return web.Response(status=401, text="invalid signature")

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return web.Response(status=400, text="invalid json")

        try:
            await self._payment_service.handle_webhook(payload)
        except Exception:
            LOGGER.exception("Webhook handling failed")
            return web.Response(status=500, text="handler error")

        return web.Response(status=200, text="ok")


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

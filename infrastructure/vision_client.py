from __future__ import annotations

import base64
from urllib.parse import parse_qs, unquote_plus, urlparse

import httpx


class VisionExtractionError(Exception):
    pass


class VisionConfigurationError(VisionExtractionError):
    pass


class VisionServiceUnavailable(VisionExtractionError):
    pass


class VisionClient:
    _ENDPOINT = "https://api.ocr.space/parse/image"

    def __init__(self, api_key: str) -> None:
        self._api_key = self._normalize_api_key(api_key)

    @staticmethod
    def _normalize_api_key(api_key: str) -> str:
        raw = (api_key or "").strip().strip('"').strip("'")
        if not raw:
            return ""

        # Allow either a raw key or a full OCR.space URL copied from docs.
        if "api.ocr.space" in raw:
            parsed = urlparse(raw)
            key = parse_qs(parsed.query).get("apikey", [""])[0].strip()
            if key:
                return key

        # If user pasted query-style config like: apikey=K123
        if "apikey=" in raw.lower():
            parts = raw.split("apikey=", 1)
            if len(parts) == 2:
                return unquote_plus(parts[1]).strip()

        return raw

    async def extract_text(self, image_bytes: bytes) -> str:
        if not self._api_key:
            raise VisionConfigurationError("OCR.space API key is missing")
        if self._api_key == "API_KEY":
            raise VisionConfigurationError(
                "OCR.space API key is set to placeholder 'API_KEY'. Replace it with a real key."
            )

        encoded = base64.b64encode(image_bytes).decode("ascii")

        form_data = {
            "apikey": self._api_key,
            "language": "eng",
            "isOverlayRequired": "false",
            "OCREngine": "2",
            "base64Image": f"data:image/jpeg;base64,{encoded}",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(self._ENDPOINT, data=form_data)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            error_detail = ""
            try:
                error_body = exc.response.json()
                messages = error_body.get("ErrorMessage", [])
                if isinstance(messages, list):
                    error_detail = "; ".join(msg for msg in messages if msg)
                elif messages:
                    error_detail = str(messages)
                if not error_detail:
                    error_detail = str(error_body)
            except Exception:  # noqa: BLE001
                error_detail = exc.response.text.strip()

            status = exc.response.status_code
            if error_detail:
                raise VisionExtractionError(
                    f"OCR.space API HTTP {status}: {error_detail}"
                ) from exc
            raise VisionExtractionError(f"OCR.space API HTTP {status}") from exc
        except httpx.TimeoutException as exc:
            raise VisionServiceUnavailable("OCR request timed out. Please try again.") from exc
        except httpx.NetworkError as exc:
            raise VisionServiceUnavailable("Cannot reach OCR.space. Check internet connection.") from exc
        except Exception as exc:  # noqa: BLE001
            raise VisionExtractionError(f"OCR extraction failed: {exc}") from exc

        if data.get("IsErroredOnProcessing"):
            messages = data.get("ErrorMessage", [])
            if isinstance(messages, list):
                detail = "; ".join(msg for msg in messages if msg)
            else:
                detail = str(messages)
            if not detail:
                detail = data.get("ErrorDetails") or "Unknown OCR.space error"
            raise VisionExtractionError(f"OCR.space API error: {detail}")

        parsed_results = data.get("ParsedResults", [])
        if not parsed_results:
            return ""

        extracted_parts: list[str] = []
        for item in parsed_results:
            parsed_text = (item or {}).get("ParsedText", "")
            if parsed_text and parsed_text.strip():
                extracted_parts.append(parsed_text.strip())

        return "\n".join(extracted_parts)

    async def validate_api_key(self) -> None:
        if not self._api_key:
            raise VisionConfigurationError("OCR.space API key is missing")
        if self._api_key == "API_KEY":
            raise VisionConfigurationError(
                "OCR.space API key is set to placeholder 'API_KEY'. Replace it with a real key."
            )

        # 1x1 transparent PNG used to validate credentials without depending on user uploads.
        probe_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2N2XkAAAAASUVORK5CYII="
        form_data = {
            "apikey": self._api_key,
            "language": "eng",
            "isOverlayRequired": "false",
            "OCREngine": "2",
            "base64Image": f"data:image/png;base64,{probe_image}",
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(self._ENDPOINT, data=form_data)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            error_detail = exc.response.text.strip() or "Unknown OCR.space error"
            if "The API key is invalid" in error_detail:
                raise VisionConfigurationError("OCR.space API key is invalid") from exc
            raise VisionServiceUnavailable(
                f"OCR.space preflight failed with HTTP {exc.response.status_code}: {error_detail}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise VisionServiceUnavailable("OCR.space preflight timed out") from exc
        except httpx.NetworkError as exc:
            raise VisionServiceUnavailable("Cannot reach OCR.space during preflight") from exc
        except Exception as exc:  # noqa: BLE001
            raise VisionServiceUnavailable(f"OCR.space preflight failed: {exc}") from exc

        if data.get("IsErroredOnProcessing"):
            messages = data.get("ErrorMessage", [])
            detail = "; ".join(messages) if isinstance(messages, list) else str(messages)
            if "The API key is invalid" in detail:
                raise VisionConfigurationError("OCR.space API key is invalid")
            raise VisionServiceUnavailable(detail or "OCR.space preflight failed")

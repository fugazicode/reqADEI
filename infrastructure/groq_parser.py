from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from groq import AsyncGroq


class GroqParsingError(Exception):
    pass


class GroqParser:
    def __init__(self, api_key: str, model: str, vision_model: str, prompts_dir: Path) -> None:
        self._client = AsyncGroq(api_key=api_key)
        self._model = model
        self._vision_model = vision_model
        self._prompts_dir = prompts_dir

    async def parse(self, raw_text: str, prompt_template_name: str) -> dict:
        prompt_path = self._prompts_dir / f"{prompt_template_name}.txt"
        if not prompt_path.exists():
            raise GroqParsingError(f"Prompt file not found: {prompt_path}")

        template = prompt_path.read_text(encoding="utf-8")
        prompt = template.replace("{raw_text}", raw_text)

        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            content = completion.choices[0].message.content or "{}"
            return self._parse_json(content)
        except Exception as exc:  # noqa: BLE001
            raise GroqParsingError(f"Groq parsing failed: {exc}") from exc

    async def parse_image(self, image_bytes_list: list[bytes], prompt_template_name: str) -> dict:
        """Vision-based parsing. Sends all images in a single Groq call and returns structured JSON."""
        prompt_path = self._prompts_dir / f"{prompt_template_name}.txt"
        if not prompt_path.exists():
            raise GroqParsingError(f"Prompt file not found: {prompt_path}")

        prompt = prompt_path.read_text(encoding="utf-8")

        content: list[dict] = []
        for image_bytes in image_bytes_list:
            encoded = base64.b64encode(image_bytes).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded}",
                },
            })
        content.append({"type": "text", "text": prompt})

        try:
            completion = await self._client.chat.completions.create(
                model=self._vision_model,
                messages=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": content},
                ],
                temperature=0,
            )
            response_content = completion.choices[0].message.content or "{}"
            return self._parse_json(response_content)
        except Exception as exc:  # noqa: BLE001
            raise GroqParsingError(f"Groq vision parsing failed: {exc}") from exc

    @staticmethod
    def _parse_json(content: str) -> dict:
        stripped = content.strip()
        fenced_match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", stripped, re.IGNORECASE)
        if fenced_match:
            stripped = fenced_match.group(1).strip()

        start_candidates = [idx for idx in (stripped.find("{"), stripped.find("[")) if idx != -1]
        end_candidates = [idx for idx in (stripped.rfind("}"), stripped.rfind("]")) if idx != -1]
        if start_candidates and end_candidates:
            start = min(start_candidates)
            end = max(end_candidates)
            if end > start:
                stripped = stripped[start : end + 1]

        return json.loads(stripped)

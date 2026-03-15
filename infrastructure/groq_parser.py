from __future__ import annotations

import json
from pathlib import Path

from groq import AsyncGroq


class GroqParsingError(Exception):
    pass


class GroqParser:
    def __init__(self, api_key: str, model: str, prompts_dir: Path) -> None:
        self._client = AsyncGroq(api_key=api_key)
        self._model = model
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

    @staticmethod
    def _parse_json(content: str) -> dict:
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
        return json.loads(stripped)

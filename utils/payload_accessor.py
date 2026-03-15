from __future__ import annotations

from typing import Any
from typing import get_args, get_origin

from pydantic import BaseModel

from shared.models.form_payload import FormPayload


class PayloadAccessor:
    @staticmethod
    def _resolve_model_type(annotation: Any) -> type[BaseModel] | None:
        origin = get_origin(annotation)
        if origin is None:
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                return annotation
            return None

        for arg in get_args(annotation):
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                return arg
        return None

    @staticmethod
    def get(payload: FormPayload, path: str) -> Any:
        current: Any = payload
        for part in path.split("."):
            if current is None:
                return None
            current = getattr(current, part, None)
        return current

    @staticmethod
    def set(payload: FormPayload, path: str, value: Any) -> None:
        parts = path.split(".")
        current: Any = payload

        for part in parts[:-1]:
            next_value = getattr(current, part, None)
            if next_value is None:
                field_info = getattr(type(current), "model_fields", {}).get(part)
                if field_info is None or field_info.annotation is None:
                    raise AttributeError(f"Cannot resolve nested path segment: {part}")

                model_type = PayloadAccessor._resolve_model_type(field_info.annotation)
                if model_type is None:
                    raise AttributeError(f"Nested path segment is not a model field: {part}")

                next_value = model_type()
                setattr(current, part, next_value)
            current = next_value

        setattr(current, parts[-1], value)

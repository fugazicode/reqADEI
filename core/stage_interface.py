from __future__ import annotations

from abc import ABC, abstractmethod

from shared.models.session import FormSession


class PipelineStage(ABC):
    name: str

    @abstractmethod
    async def execute(self, session: FormSession) -> FormSession:
        raise NotImplementedError

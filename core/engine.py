from __future__ import annotations

from typing import Iterable

from core.stage_interface import PipelineStage
from shared.models.session import FormSession


class PipelineEngine:
    def __init__(self, stages: Iterable[PipelineStage]) -> None:
        self._stages = list(stages)
        self.stage_order = ["parse_image"]

        stage_names = [stage.name for stage in self._stages]
        if len(stage_names) != len(set(stage_names)):
            raise ValueError("Duplicate stage names are not supported.")

    async def run(self, session: FormSession) -> FormSession:
        session.last_error = None
        executed: set[str] = set()

        ordered_stages: list[PipelineStage] = []
        for stage_name in self.stage_order:
            for stage in self._stages:
                if stage.name == stage_name and stage.name not in executed:
                    ordered_stages.append(stage)
                    executed.add(stage.name)

        for stage in self._stages:
            if stage.name not in executed:
                ordered_stages.append(stage)
                executed.add(stage.name)

        for stage in ordered_stages:
            try:
                session = await stage.execute(session)
            except Exception as exc:  # noqa: BLE001
                session.last_error = str(exc)
                return session
        return session

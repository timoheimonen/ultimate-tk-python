from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent


class PlatformBackend(Protocol):
    def startup(self, context: GameContext) -> None: ...

    def poll_events(self) -> Sequence[AppEvent]: ...

    def present(self, context: GameContext, scene_name: str, alpha: float) -> None: ...

    def shutdown(self, context: GameContext) -> None: ...


@dataclass(slots=True)
class HeadlessPlatformBackend:
    status_print_interval: int = 0

    def startup(self, context: GameContext) -> None:
        context.logger.info("Headless runtime backend started")

    def poll_events(self) -> Sequence[AppEvent]:
        return ()

    def present(self, context: GameContext, scene_name: str, alpha: float) -> None:
        del alpha
        if self.status_print_interval <= 0:
            return

        frame = context.runtime.render_frame
        if frame % self.status_print_interval != 0:
            return

        context.logger.info(
            "frame=%d mode=%s scene=%s sim=%d elapsed=%.3f render=%dx%d digest=%08x",
            frame,
            context.runtime.mode.value,
            scene_name,
            context.runtime.simulation_frame,
            context.runtime.elapsed_seconds,
            context.runtime.last_render_width,
            context.runtime.last_render_height,
            context.runtime.last_render_digest,
        )

    def shutdown(self, context: GameContext) -> None:
        context.logger.info("Headless runtime backend stopped")

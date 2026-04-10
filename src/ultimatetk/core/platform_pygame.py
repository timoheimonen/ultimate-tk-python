from __future__ import annotations

from dataclasses import dataclass
import importlib
from typing import Any, Sequence

from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent


@dataclass(slots=True)
class PygamePlatformBackend:
    status_print_interval: int = 0
    input_schedule: dict[int, tuple[AppEvent, ...]] | None = None
    _pygame: Any | None = None
    _poll_frame: int = 0

    def startup(self, context: GameContext) -> None:
        self._poll_frame = 0
        try:
            pygame_module = importlib.import_module("pygame")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Pygame backend requested but 'pygame' is not installed. "
                "Install it with: pip install pygame",
            ) from exc

        self._pygame = pygame_module
        context.logger.info(
            "Pygame runtime backend initialized (workstream 1 stub)",
        )

    def poll_events(self) -> Sequence[AppEvent]:
        if self.input_schedule is None:
            self._poll_frame += 1
            return ()

        events = self.input_schedule.get(self._poll_frame, ())
        self._poll_frame += 1
        return events

    def present(self, context: GameContext, scene_name: str, alpha: float) -> None:
        del context
        del scene_name
        del alpha

    def shutdown(self, context: GameContext) -> None:
        if self._pygame is not None:
            try:
                self._pygame.quit()
            except Exception:  # pragma: no cover - defensive shutdown path
                pass
        self._pygame = None
        context.logger.info("Pygame runtime backend stopped")

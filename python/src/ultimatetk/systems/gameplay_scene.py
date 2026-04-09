from __future__ import annotations

from ultimatetk.core.context import GameContext
from ultimatetk.core.scenes import BaseScene
from ultimatetk.core.state import AppMode


class GameplayScene(BaseScene):
    name = "gameplay"

    def __init__(self) -> None:
        self._ticks = 0

    def on_enter(self, context: GameContext) -> None:
        context.runtime.mode = AppMode.GAMEPLAY
        context.logger.info("Entered gameplay scene scaffold")

    def update(self, context: GameContext, dt_seconds: float):
        del context
        del dt_seconds
        self._ticks += 1
        return None

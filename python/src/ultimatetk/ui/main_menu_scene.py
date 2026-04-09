from __future__ import annotations

from ultimatetk.core.context import GameContext
from ultimatetk.core.scenes import BaseScene, SceneTransition
from ultimatetk.core.state import AppMode


class MainMenuScene(BaseScene):
    name = "main_menu"

    def __init__(self) -> None:
        self._did_autostart = False

    def on_enter(self, context: GameContext) -> None:
        context.runtime.mode = AppMode.MAIN_MENU
        context.logger.info("Entered main menu scene scaffold")

    def update(self, context: GameContext, dt_seconds: float) -> SceneTransition | None:
        del dt_seconds
        if not context.config.autostart_gameplay:
            return None
        if self._did_autostart:
            return None

        self._did_autostart = True
        from ultimatetk.systems.gameplay_scene import GameplayScene

        return SceneTransition(next_scene=GameplayScene())

from __future__ import annotations

from ultimatetk.core.context import GameContext
from ultimatetk.core.scenes import BaseScene, SceneTransition
from ultimatetk.core.state import AppMode


class BootScene(BaseScene):
    name = "boot"

    def on_enter(self, context: GameContext) -> None:
        context.runtime.mode = AppMode.BOOT
        context.logger.info("Boot scene initialized")

    def update(self, context: GameContext, dt_seconds: float) -> SceneTransition | None:
        del context
        del dt_seconds
        from ultimatetk.ui.main_menu_scene import MainMenuScene

        return SceneTransition(next_scene=MainMenuScene())

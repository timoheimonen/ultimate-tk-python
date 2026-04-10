from __future__ import annotations

from typing import Sequence

from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent, EventType, InputAction
from ultimatetk.core.scenes import BaseScene, SceneTransition
from ultimatetk.core.state import AppMode


class MainMenuScene(BaseScene):
    name = "main_menu"
    _MENU_ENTRIES: tuple[str, ...] = ("start", "quit")
    _ACTION_PREVIOUS = frozenset((InputAction.MOVE_FORWARD, InputAction.TURN_LEFT, InputAction.STRAFE_LEFT))
    _ACTION_NEXT = frozenset((InputAction.MOVE_BACKWARD, InputAction.TURN_RIGHT, InputAction.STRAFE_RIGHT))
    _ACTION_CONFIRM = frozenset((InputAction.SHOOT, InputAction.TOGGLE_SHOP, InputAction.NEXT_WEAPON))

    def __init__(self, *, autostart_enabled: bool = True) -> None:
        self._did_autostart = False
        self._autostart_enabled = autostart_enabled
        self._selected_index = 0

    def on_enter(self, context: GameContext) -> None:
        context.runtime.mode = AppMode.MAIN_MENU
        self._selected_index = 0
        context.logger.info("Entered main menu scene")

    def handle_events(self, context: GameContext, events: Sequence[AppEvent]) -> SceneTransition | None:
        for event in events:
            if event.type == EventType.QUIT:
                return SceneTransition(quit_requested=True)

            if event.type != EventType.ACTION_PRESSED or event.action is None:
                continue

            if event.action in self._ACTION_PREVIOUS:
                self._selected_index = (self._selected_index - 1) % len(self._MENU_ENTRIES)
                context.logger.info("Main menu selected: %s", self._MENU_ENTRIES[self._selected_index])
                continue

            if event.action in self._ACTION_NEXT:
                self._selected_index = (self._selected_index + 1) % len(self._MENU_ENTRIES)
                context.logger.info("Main menu selected: %s", self._MENU_ENTRIES[self._selected_index])
                continue

            if event.action in self._ACTION_CONFIRM:
                if self._selected_index == 1:
                    context.logger.info("Main menu quit selected")
                    return SceneTransition(quit_requested=True)
                context.logger.info("Main menu start selected")
                from ultimatetk.systems.gameplay_scene import GameplayScene

                return SceneTransition(next_scene=GameplayScene())

        return None

    def update(self, context: GameContext, dt_seconds: float) -> SceneTransition | None:
        del dt_seconds
        if not self._autostart_enabled:
            return None
        if not context.config.autostart_gameplay:
            return None
        if self._did_autostart:
            return None

        self._did_autostart = True
        context.logger.info("Main menu autostart transitioning to gameplay")
        from ultimatetk.systems.gameplay_scene import GameplayScene

        return SceneTransition(next_scene=GameplayScene())

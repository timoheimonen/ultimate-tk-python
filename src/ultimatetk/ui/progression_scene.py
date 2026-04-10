from __future__ import annotations

from typing import Sequence

from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent, EventType, InputAction
from ultimatetk.core.scenes import BaseScene, SceneTransition
from ultimatetk.core.state import AppMode


_CONFIRM_ACTIONS = frozenset((InputAction.SHOOT, InputAction.TOGGLE_SHOP, InputAction.NEXT_WEAPON))


class LevelCompleteScene(BaseScene):
    name = "level_complete"
    _RETURN_TICKS = 20

    def __init__(self, *, from_level_index: int, to_level_index: int) -> None:
        self._from_level_index = max(0, from_level_index)
        self._to_level_index = max(0, to_level_index)
        self._ticks_remaining = self._RETURN_TICKS

    def on_enter(self, context: GameContext) -> None:
        self._ticks_remaining = self._RETURN_TICKS
        context.runtime.mode = AppMode.LEVEL_COMPLETE
        context.runtime.progression_event = "level_complete"
        context.runtime.progression_from_level_index = self._from_level_index
        context.runtime.progression_to_level_index = self._to_level_index
        context.runtime.progression_has_next_level = True
        context.runtime.progression_ticks_remaining = self._ticks_remaining
        context.logger.info(
            "Level complete scene entered: level %d -> %d (%d ticks)",
            self._from_level_index + 1,
            self._to_level_index + 1,
            self._RETURN_TICKS,
        )

    def handle_events(self, context: GameContext, events: Sequence[AppEvent]) -> SceneTransition | None:
        for event in events:
            if event.type == EventType.QUIT:
                return SceneTransition(quit_requested=True)
            if event.type == EventType.ACTION_PRESSED and event.action in _CONFIRM_ACTIONS:
                self._ticks_remaining = 0
                context.runtime.progression_ticks_remaining = 0
                break
        return None

    def update(self, context: GameContext, dt_seconds: float) -> SceneTransition | None:
        del dt_seconds
        context.runtime.mode = AppMode.LEVEL_COMPLETE
        if self._ticks_remaining > 0:
            self._ticks_remaining -= 1
        context.runtime.progression_ticks_remaining = self._ticks_remaining
        if self._ticks_remaining > 0:
            return None

        context.session.level_index = self._to_level_index
        context.logger.info("Level complete scene finished, entering level %d", context.session.level_index + 1)
        from ultimatetk.systems.gameplay_scene import GameplayScene

        return SceneTransition(next_scene=GameplayScene())


class RunCompleteScene(BaseScene):
    name = "run_complete"
    _RETURN_TICKS = 30

    def __init__(self, *, completed_level_index: int) -> None:
        self._completed_level_index = max(0, completed_level_index)
        self._ticks_remaining = self._RETURN_TICKS

    def on_enter(self, context: GameContext) -> None:
        self._ticks_remaining = self._RETURN_TICKS
        context.runtime.mode = AppMode.RUN_COMPLETE
        context.runtime.progression_event = "run_complete"
        context.runtime.progression_from_level_index = self._completed_level_index
        context.runtime.progression_to_level_index = 0
        context.runtime.progression_has_next_level = False
        context.runtime.progression_ticks_remaining = self._ticks_remaining
        context.logger.info(
            "Run complete scene entered after level %d (%d ticks)",
            self._completed_level_index + 1,
            self._RETURN_TICKS,
        )

    def handle_events(self, context: GameContext, events: Sequence[AppEvent]) -> SceneTransition | None:
        for event in events:
            if event.type == EventType.QUIT:
                return SceneTransition(quit_requested=True)
            if event.type == EventType.ACTION_PRESSED and event.action in _CONFIRM_ACTIONS:
                self._ticks_remaining = 0
                context.runtime.progression_ticks_remaining = 0
                break
        return None

    def update(self, context: GameContext, dt_seconds: float) -> SceneTransition | None:
        del dt_seconds
        context.runtime.mode = AppMode.RUN_COMPLETE
        if self._ticks_remaining > 0:
            self._ticks_remaining -= 1
        context.runtime.progression_ticks_remaining = self._ticks_remaining
        if self._ticks_remaining > 0:
            return None

        context.session.level_index = 0
        context.logger.info("Run complete scene finished, returning to main menu")
        from ultimatetk.ui.main_menu_scene import MainMenuScene

        return SceneTransition(next_scene=MainMenuScene(autostart_enabled=False))

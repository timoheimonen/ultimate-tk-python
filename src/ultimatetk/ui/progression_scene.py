from __future__ import annotations

from typing import Sequence

from ultimatetk.assets.repository import GameDataRepository
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent, EventType, InputAction
from ultimatetk.core.scenes import BaseScene, SceneTransition
from ultimatetk.core.state import AppMode
from ultimatetk.formats.fnt import FontFile
from ultimatetk.rendering import SCREEN_HEIGHT, SCREEN_WIDTH, frame_digest
from ultimatetk.ui.software_ui import fallback_palette_bytes, render_progress_frame


_CONFIRM_ACTIONS = frozenset((InputAction.SHOOT, InputAction.TOGGLE_SHOP, InputAction.NEXT_WEAPON))


class LevelCompleteScene(BaseScene):
    name = "level_complete"
    _RETURN_TICKS = 20

    def __init__(self, *, from_level_index: int, to_level_index: int) -> None:
        self._from_level_index = max(0, from_level_index)
        self._to_level_index = max(0, to_level_index)
        self._ticks_remaining = self._RETURN_TICKS
        self._ui_font: FontFile | None = None
        self._palette_bytes: bytes = fallback_palette_bytes()

    def on_enter(self, context: GameContext) -> None:
        self._ticks_remaining = self._RETURN_TICKS
        self._ui_font = _load_ui_font(context)
        self._palette_bytes = _load_palette_bytes(context)
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

    def on_exit(self, context: GameContext) -> None:
        del context
        self._ui_font = None

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

    def render(self, context: GameContext, alpha: float) -> None:
        del alpha
        detail = f"LEVEL {self._from_level_index + 1} -> {self._to_level_index + 1}"
        hint = "PRESS SPACE / TAB / ENTER"
        pixels = render_progress_frame(
            font=self._ui_font,
            title="Level complete",
            detail=detail,
            hint=hint,
        )
        context.runtime.last_render_width = SCREEN_WIDTH
        context.runtime.last_render_height = SCREEN_HEIGHT
        context.runtime.last_render_pixels = pixels
        context.runtime.last_render_palette = self._palette_bytes
        context.runtime.last_render_digest = frame_digest(pixels)


class RunCompleteScene(BaseScene):
    name = "run_complete"
    _RETURN_TICKS = 30

    def __init__(self, *, completed_level_index: int) -> None:
        self._completed_level_index = max(0, completed_level_index)
        self._ticks_remaining = self._RETURN_TICKS
        self._ui_font: FontFile | None = None
        self._palette_bytes: bytes = fallback_palette_bytes()

    def on_enter(self, context: GameContext) -> None:
        self._ticks_remaining = self._RETURN_TICKS
        self._ui_font = _load_ui_font(context)
        self._palette_bytes = _load_palette_bytes(context)
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

    def on_exit(self, context: GameContext) -> None:
        del context
        self._ui_font = None

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

    def render(self, context: GameContext, alpha: float) -> None:
        del alpha
        detail = f"CLEARED THROUGH LEVEL {self._completed_level_index + 1}"
        hint = "PRESS SPACE / TAB / ENTER"
        pixels = render_progress_frame(
            font=self._ui_font,
            title="Run complete",
            detail=detail,
            hint=hint,
        )
        context.runtime.last_render_width = SCREEN_WIDTH
        context.runtime.last_render_height = SCREEN_HEIGHT
        context.runtime.last_render_pixels = pixels
        context.runtime.last_render_palette = self._palette_bytes
        context.runtime.last_render_digest = frame_digest(pixels)


def _load_ui_font(context: GameContext) -> FontFile | None:
    repo = GameDataRepository(context.paths)
    for font_name in ("8X8.FNT", "8X8B.FNT"):
        try:
            return repo.load_fnt(font_name)
        except FileNotFoundError:
            continue
    return None


def _load_palette_bytes(context: GameContext) -> bytes:
    repo = GameDataRepository(context.paths)
    try:
        wall_sheet = repo.load_efp("WALLS1.EFP")
        return wall_sheet.palette
    except FileNotFoundError:
        return fallback_palette_bytes()

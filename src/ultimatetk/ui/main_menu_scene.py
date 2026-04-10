from __future__ import annotations

from typing import Sequence

from ultimatetk.assets.repository import GameDataRepository
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent, EventType, InputAction
from ultimatetk.core.scenes import BaseScene, SceneTransition
from ultimatetk.core.state import AppMode
from ultimatetk.formats.fnt import FontFile
from ultimatetk.rendering import SCREEN_HEIGHT, SCREEN_WIDTH, frame_digest
from ultimatetk.ui.software_ui import fallback_palette_bytes, render_menu_frame


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
        self._ui_font: FontFile | None = None
        self._palette_bytes: bytes = fallback_palette_bytes()

    def on_enter(self, context: GameContext) -> None:
        context.runtime.mode = AppMode.MAIN_MENU
        self._selected_index = 0
        self._ui_font = self._load_ui_font(context)
        self._palette_bytes = self._load_palette_bytes(context)
        context.logger.info("Entered main menu scene")

    def on_exit(self, context: GameContext) -> None:
        del context
        self._ui_font = None

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

    def render(self, context: GameContext, alpha: float) -> None:
        del alpha
        pixels = render_menu_frame(
            font=self._ui_font,
            selected_index=self._selected_index,
            entries=self._MENU_ENTRIES,
        )
        context.runtime.last_render_width = SCREEN_WIDTH
        context.runtime.last_render_height = SCREEN_HEIGHT
        context.runtime.last_render_pixels = pixels
        context.runtime.last_render_palette = self._palette_bytes
        context.runtime.last_render_digest = frame_digest(pixels)

    def _load_ui_font(self, context: GameContext) -> FontFile | None:
        repo = GameDataRepository(context.paths)
        for font_name in ("8X8.FNT", "8X8B.FNT"):
            try:
                return repo.load_fnt(font_name)
            except FileNotFoundError:
                continue
        return None

    def _load_palette_bytes(self, context: GameContext) -> bytes:
        repo = GameDataRepository(context.paths)
        try:
            wall_sheet = repo.load_efp("WALLS1.EFP")
            return wall_sheet.palette
        except FileNotFoundError:
            return fallback_palette_bytes()

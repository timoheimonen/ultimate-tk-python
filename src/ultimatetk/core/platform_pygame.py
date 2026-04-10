from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from typing import Any, Sequence

from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent, EventType, InputAction
from ultimatetk.rendering import SCREEN_HEIGHT, SCREEN_WIDTH, indexed_to_rgb24


@dataclass(slots=True)
class PygamePlatformBackend:
    status_print_interval: int = 0
    window_scale: int = 3
    input_schedule: dict[int, tuple[AppEvent, ...]] | None = None
    _pygame: Any | None = None
    _window: Any | None = None
    _window_size: tuple[int, int] = (SCREEN_WIDTH * 3, SCREEN_HEIGHT * 3)
    _poll_frame: int = 0
    _active_actions: set[InputAction] = field(default_factory=set)
    _key_to_action: dict[int, InputAction] = field(default_factory=dict)
    _key_to_weapon_slot: dict[int, int] = field(default_factory=dict)

    def startup(self, context: GameContext) -> None:
        self._poll_frame = 0
        self._active_actions.clear()

        try:
            pygame_module = importlib.import_module("pygame")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Pygame backend requested but 'pygame' is not installed. "
                "Install it with: pip install pygame",
            ) from exc

        self._pygame = pygame_module
        if self.window_scale <= 0:
            raise ValueError("pygame window scale must be >= 1")

        self._window_size = (
            SCREEN_WIDTH * self.window_scale,
            SCREEN_HEIGHT * self.window_scale,
        )

        pygame_module.init()
        pygame_module.key.set_repeat()
        self._window = pygame_module.display.set_mode(self._window_size)
        pygame_module.display.set_caption("Ultimate TK (pygame)")
        self._build_key_maps(pygame_module)
        context.logger.info(
            "Pygame runtime backend started (%dx%d, scale=%d)",
            self._window_size[0],
            self._window_size[1],
            self.window_scale,
        )

    def poll_events(self) -> Sequence[AppEvent]:
        events: list[AppEvent] = []
        if self.input_schedule is not None:
            events.extend(self.input_schedule.get(self._poll_frame, ()))

        if self._pygame is None:
            self._poll_frame += 1
            return tuple(events)

        for pygame_event in self._pygame.event.get():
            event_type = pygame_event.type
            if event_type == self._pygame.QUIT:
                events.append(AppEvent(type=EventType.QUIT))
                continue

            if event_type == getattr(self._pygame, "MOUSEWHEEL", None):
                wheel_steps = abs(int(getattr(pygame_event, "y", 0)))
                if wheel_steps <= 0:
                    continue
                for _ in range(wheel_steps):
                    events.append(AppEvent.action_pressed(InputAction.NEXT_WEAPON))
                continue

            if event_type == self._pygame.KEYDOWN:
                key = pygame_event.key
                if key == self._pygame.K_ESCAPE:
                    events.append(AppEvent(type=EventType.QUIT))
                    continue

                weapon_slot = self._key_to_weapon_slot.get(key)
                if weapon_slot is not None:
                    events.append(AppEvent.weapon_select(weapon_slot))
                    continue

                action = self._key_to_action.get(key)
                if action is None:
                    continue
                if action in self._active_actions:
                    continue

                self._active_actions.add(action)
                events.append(AppEvent.action_pressed(action))
                continue

            if event_type == self._pygame.KEYUP:
                action = self._key_to_action.get(pygame_event.key)
                if action is None:
                    continue
                if action not in self._active_actions:
                    continue

                self._active_actions.remove(action)
                events.append(AppEvent.action_released(action))

        self._poll_frame += 1
        return tuple(events)

    def present(self, context: GameContext, scene_name: str, alpha: float) -> None:
        del scene_name
        del alpha
        if self._pygame is None or self._window is None:
            return

        width = context.runtime.last_render_width
        height = context.runtime.last_render_height
        pixels = context.runtime.last_render_pixels
        palette = context.runtime.last_render_palette

        if (
            width <= 0
            or height <= 0
            or len(pixels) != width * height
            or len(palette) != 256 * 3
        ):
            self._window.fill((0, 0, 0))
            self._pygame.display.flip()
            return

        rgb = indexed_to_rgb24(pixels, palette)
        frame_surface = self._pygame.image.frombuffer(rgb, (width, height), "RGB")
        if (width, height) != self._window_size:
            frame_surface = self._pygame.transform.scale(frame_surface, self._window_size)

        self._window.blit(frame_surface, (0, 0))
        self._pygame.display.flip()

    def shutdown(self, context: GameContext) -> None:
        self._active_actions.clear()
        self._window = None
        if self._pygame is not None:
            self._pygame.quit()
        self._pygame = None
        context.logger.info("Pygame runtime backend stopped")

    def _build_key_maps(self, pygame_module: Any) -> None:
        self._key_to_action = {
            pygame_module.K_w: InputAction.MOVE_FORWARD,
            pygame_module.K_UP: InputAction.MOVE_FORWARD,
            pygame_module.K_s: InputAction.MOVE_BACKWARD,
            pygame_module.K_DOWN: InputAction.MOVE_BACKWARD,
            pygame_module.K_a: InputAction.TURN_LEFT,
            pygame_module.K_LEFT: InputAction.TURN_LEFT,
            pygame_module.K_d: InputAction.TURN_RIGHT,
            pygame_module.K_RIGHT: InputAction.TURN_RIGHT,
            pygame_module.K_q: InputAction.STRAFE_LEFT,
            pygame_module.K_e: InputAction.STRAFE_RIGHT,
            pygame_module.K_z: InputAction.STRAFE_MODIFIER,
            pygame_module.K_SPACE: InputAction.SHOOT,
            pygame_module.K_TAB: InputAction.NEXT_WEAPON,
            pygame_module.K_r: InputAction.TOGGLE_SHOP,
            pygame_module.K_RETURN: InputAction.TOGGLE_SHOP,
        }

        page_up = getattr(pygame_module, "K_PAGEUP", None)
        page_down = getattr(pygame_module, "K_PAGEDOWN", None)
        if page_up is not None:
            self._key_to_action[page_up] = InputAction.NEXT_WEAPON
        if page_down is not None:
            self._key_to_action[page_down] = InputAction.NEXT_WEAPON

        self._key_to_weapon_slot = {
            pygame_module.K_BACKQUOTE: 0,
            pygame_module.K_1: 1,
            pygame_module.K_2: 2,
            pygame_module.K_3: 3,
            pygame_module.K_4: 4,
            pygame_module.K_5: 5,
            pygame_module.K_6: 6,
            pygame_module.K_7: 7,
            pygame_module.K_8: 8,
            pygame_module.K_9: 9,
            pygame_module.K_0: 10,
            pygame_module.K_MINUS: 11,
            pygame_module.K_EQUALS: 11,
        }

        self._bind_optional_weapon_key(pygame_module, "K_KP1", 1)
        self._bind_optional_weapon_key(pygame_module, "K_KP2", 2)
        self._bind_optional_weapon_key(pygame_module, "K_KP3", 3)
        self._bind_optional_weapon_key(pygame_module, "K_KP4", 4)
        self._bind_optional_weapon_key(pygame_module, "K_KP5", 5)
        self._bind_optional_weapon_key(pygame_module, "K_KP6", 6)
        self._bind_optional_weapon_key(pygame_module, "K_KP7", 7)
        self._bind_optional_weapon_key(pygame_module, "K_KP8", 8)
        self._bind_optional_weapon_key(pygame_module, "K_KP9", 9)
        self._bind_optional_weapon_key(pygame_module, "K_KP0", 10)
        self._bind_optional_weapon_key(pygame_module, "K_KP_MINUS", 11)
        self._bind_optional_weapon_key(pygame_module, "K_KP_PLUS", 11)

        self._bind_optional_weapon_key(pygame_module, "K_F1", 0)
        self._bind_optional_weapon_key(pygame_module, "K_F2", 1)
        self._bind_optional_weapon_key(pygame_module, "K_F3", 2)
        self._bind_optional_weapon_key(pygame_module, "K_F4", 3)
        self._bind_optional_weapon_key(pygame_module, "K_F5", 4)
        self._bind_optional_weapon_key(pygame_module, "K_F6", 5)
        self._bind_optional_weapon_key(pygame_module, "K_F7", 6)
        self._bind_optional_weapon_key(pygame_module, "K_F8", 7)
        self._bind_optional_weapon_key(pygame_module, "K_F9", 8)
        self._bind_optional_weapon_key(pygame_module, "K_F10", 9)
        self._bind_optional_weapon_key(pygame_module, "K_F11", 10)
        self._bind_optional_weapon_key(pygame_module, "K_F12", 11)

    def _bind_optional_weapon_key(self, pygame_module: Any, key_name: str, weapon_slot: int) -> None:
        key = getattr(pygame_module, key_name, None)
        if key is None:
            return
        self._key_to_weapon_slot[key] = weapon_slot

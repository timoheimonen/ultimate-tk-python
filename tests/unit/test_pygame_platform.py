from __future__ import annotations

import logging
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import EventType, InputAction
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.platform_pygame import PygamePlatformBackend
from ultimatetk.rendering import SCREEN_HEIGHT, SCREEN_WIDTH


def _context() -> GameContext:
    return GameContext(
        config=RuntimeConfig(platform="pygame"),
        paths=GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        ),
        logger=logging.getLogger("ultimatetk.test.pygame"),
    )


class _FakeWindow:
    def __init__(self) -> None:
        self.fill_calls: list[tuple[int, int, int]] = []
        self.blit_calls: list[tuple[object, tuple[int, int]]] = []

    def fill(self, color: tuple[int, int, int]) -> None:
        self.fill_calls.append(color)

    def blit(self, surface: object, pos: tuple[int, int]) -> None:
        self.blit_calls.append((surface, pos))


class _FakeDisplay:
    def __init__(self, window: _FakeWindow) -> None:
        self.window = window
        self.mode_calls: list[tuple[int, int]] = []
        self.caption_calls: list[str] = []
        self.flip_count = 0

    def set_mode(self, size: tuple[int, int]) -> _FakeWindow:
        self.mode_calls.append(size)
        return self.window

    def set_caption(self, caption: str) -> None:
        self.caption_calls.append(caption)

    def flip(self) -> None:
        self.flip_count += 1


class _FakeKey:
    def __init__(self) -> None:
        self.set_repeat_calls = 0

    def set_repeat(self) -> None:
        self.set_repeat_calls += 1


class _FakeImage:
    def __init__(self) -> None:
        self.frombuffer_calls: list[tuple[int, tuple[int, int], str]] = []

    def frombuffer(self, rgb: bytes, size: tuple[int, int], mode: str) -> object:
        self.frombuffer_calls.append((len(rgb), size, mode))
        return ("surface", size)


class _FakeTransform:
    def __init__(self) -> None:
        self.scale_calls: list[tuple[object, tuple[int, int]]] = []

    def scale(self, surface: object, size: tuple[int, int]) -> object:
        self.scale_calls.append((surface, size))
        return ("scaled", size)


class _FakeEventQueue:
    def __init__(self, events: list[object] | None = None) -> None:
        self._events = list(events or [])

    def get(self) -> list[object]:
        events = self._events
        self._events = []
        return events


def _fake_pygame(events: list[object] | None = None) -> SimpleNamespace:
    window = _FakeWindow()
    display = _FakeDisplay(window)
    key = _FakeKey()
    image = _FakeImage()
    transform = _FakeTransform()
    event_queue = _FakeEventQueue(events)

    fake_pygame = SimpleNamespace(
        QUIT=100,
        KEYDOWN=101,
        KEYUP=102,
        K_ESCAPE=27,
        K_w=119,
        K_UP=273,
        K_s=115,
        K_DOWN=274,
        K_a=97,
        K_LEFT=276,
        K_d=100,
        K_RIGHT=275,
        K_q=113,
        K_e=101,
        K_z=122,
        K_SPACE=32,
        K_TAB=9,
        K_r=114,
        K_RETURN=13,
        K_BACKQUOTE=96,
        K_1=49,
        K_2=50,
        K_3=51,
        K_4=52,
        K_5=53,
        K_6=54,
        K_7=55,
        K_8=56,
        K_9=57,
        K_0=48,
        K_MINUS=45,
        K_EQUALS=61,
        init=lambda: None,
        quit=lambda: None,
        key=key,
        display=display,
        event=event_queue,
        image=image,
        transform=transform,
    )

    return fake_pygame


class PygamePlatformBackendTests(unittest.TestCase):
    def test_startup_raises_clear_error_when_pygame_missing(self) -> None:
        backend = PygamePlatformBackend()
        context = _context()

        with patch(
            "ultimatetk.core.platform_pygame.importlib.import_module",
            side_effect=ModuleNotFoundError("No module named 'pygame'"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Install it with: pip install pygame"):
                backend.startup(context)

    def test_startup_imports_pygame_only_on_backend_start(self) -> None:
        backend = PygamePlatformBackend()
        context = _context()
        fake_pygame = _fake_pygame()

        with patch(
            "ultimatetk.core.platform_pygame.importlib.import_module",
            return_value=fake_pygame,
        ) as import_module:
            backend.startup(context)
            import_module.assert_called_once_with("pygame")

    def test_poll_events_maps_action_weapon_and_quit(self) -> None:
        event_down = SimpleNamespace(type=101, key=119)  # KEYDOWN K_w
        event_up = SimpleNamespace(type=102, key=119)  # KEYUP K_w
        event_weapon = SimpleNamespace(type=101, key=49)  # KEYDOWN K_1
        event_escape = SimpleNamespace(type=101, key=27)  # KEYDOWN K_ESCAPE

        fake_pygame = _fake_pygame(events=[event_down, event_up, event_weapon, event_escape])
        backend = PygamePlatformBackend()
        context = _context()

        with patch(
            "ultimatetk.core.platform_pygame.importlib.import_module",
            return_value=fake_pygame,
        ):
            backend.startup(context)

        events = tuple(backend.poll_events())
        self.assertEqual(events[0].type, EventType.ACTION_PRESSED)
        self.assertEqual(events[0].action, InputAction.MOVE_FORWARD)
        self.assertEqual(events[1].type, EventType.ACTION_RELEASED)
        self.assertEqual(events[1].action, InputAction.MOVE_FORWARD)
        self.assertEqual(events[2].type, EventType.WEAPON_SELECT)
        self.assertEqual(events[2].weapon_slot, 1)
        self.assertEqual(events[3].type, EventType.QUIT)

    def test_present_blits_scaled_frame_when_payload_is_valid(self) -> None:
        fake_pygame = _fake_pygame()
        backend = PygamePlatformBackend(window_scale=2)
        context = _context()
        context.runtime.last_render_width = SCREEN_WIDTH
        context.runtime.last_render_height = SCREEN_HEIGHT
        context.runtime.last_render_pixels = bytes(SCREEN_WIDTH * SCREEN_HEIGHT)
        context.runtime.last_render_palette = bytes(256 * 3)

        with patch(
            "ultimatetk.core.platform_pygame.importlib.import_module",
            return_value=fake_pygame,
        ):
            backend.startup(context)

        backend.present(context, scene_name="gameplay", alpha=0.0)

        self.assertEqual(len(fake_pygame.image.frombuffer_calls), 1)
        self.assertEqual(len(fake_pygame.transform.scale_calls), 1)
        self.assertEqual(len(fake_pygame.display.window.blit_calls), 1)
        self.assertEqual(fake_pygame.display.flip_count, 1)

    def test_present_fills_black_when_frame_payload_is_missing(self) -> None:
        fake_pygame = _fake_pygame()
        backend = PygamePlatformBackend(window_scale=2)
        context = _context()

        with patch(
            "ultimatetk.core.platform_pygame.importlib.import_module",
            return_value=fake_pygame,
        ):
            backend.startup(context)

        backend.present(context, scene_name="main_menu", alpha=0.0)

        self.assertEqual(fake_pygame.display.window.fill_calls, [(0, 0, 0)])
        self.assertEqual(fake_pygame.display.flip_count, 1)


if __name__ == "__main__":
    unittest.main()

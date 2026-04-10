from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.app import GameApplication
from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.platform import HeadlessPlatformBackend, TerminalPlatformBackend
from ultimatetk.core.platform_pygame import PygamePlatformBackend


def _paths() -> GamePaths:
    return GamePaths(
        python_root=PROJECT_ROOT,
        game_data_root=PROJECT_ROOT / "game_data",
        runs_root=PROJECT_ROOT / "runs",
    )


class AppPlatformSelectionTests(unittest.TestCase):
    def test_defaults_to_headless_backend(self) -> None:
        app = GameApplication.create(config=RuntimeConfig(), paths=_paths())
        self.assertIsInstance(app.platform, HeadlessPlatformBackend)

    def test_selects_terminal_backend(self) -> None:
        app = GameApplication.create(
            config=RuntimeConfig(platform="terminal"),
            paths=_paths(),
        )
        self.assertIsInstance(app.platform, TerminalPlatformBackend)

    def test_selects_pygame_backend(self) -> None:
        app = GameApplication.create(
            config=RuntimeConfig(platform="pygame"),
            paths=_paths(),
        )
        self.assertIsInstance(app.platform, PygamePlatformBackend)
        self.assertEqual(app.platform.window_scale, 3)

    def test_pygame_backend_applies_window_scale(self) -> None:
        app = GameApplication.create(
            config=RuntimeConfig(platform="pygame", pygame_window_scale=2),
            paths=_paths(),
        )
        self.assertIsInstance(app.platform, PygamePlatformBackend)
        self.assertEqual(app.platform.window_scale, 2)

    def test_rejects_non_positive_pygame_window_scale(self) -> None:
        with self.assertRaises(ValueError):
            GameApplication.create(
                config=RuntimeConfig(platform="pygame", pygame_window_scale=0),
                paths=_paths(),
            )

    def test_invalid_platform_raises(self) -> None:
        with self.assertRaises(ValueError):
            GameApplication.create(
                config=RuntimeConfig(platform="invalid"),
                paths=_paths(),
            )


if __name__ == "__main__":
    unittest.main()

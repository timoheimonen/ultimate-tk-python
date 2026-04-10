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
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.platform_pygame import PygamePlatformBackend


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
        fake_pygame = SimpleNamespace(quit=lambda: None)

        with patch(
            "ultimatetk.core.platform_pygame.importlib.import_module",
            return_value=fake_pygame,
        ) as import_module:
            backend.startup(context)
            import_module.assert_called_once_with("pygame")


if __name__ == "__main__":
    unittest.main()

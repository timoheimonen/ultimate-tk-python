from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.boot_scene import BootScene
from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.context import GameContext
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.scenes import SceneManager


class SceneFlowTests(unittest.TestCase):
    def test_boot_to_menu_to_gameplay_autostart(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        self.assertEqual(manager.current_scene_name, "boot")
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

    def test_gameplay_death_returns_to_main_menu_without_autostart_loop(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.dead = True
        player.health = 0.0

        for _ in range(120):
            manager.update(0.025)
            if manager.current_scene_name == "main_menu":
                break

        self.assertEqual(manager.current_scene_name, "main_menu")

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")


if __name__ == "__main__":
    unittest.main()

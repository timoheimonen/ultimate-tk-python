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
from ultimatetk.systems.combat import CrateState
from ultimatetk.systems.player_control import grant_bullet_ammo


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

    def test_gameplay_collects_touching_crate_and_updates_runtime_counter(self) -> None:
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
        crates = getattr(gameplay_scene, "_crates", None)
        if player is None or crates is None:
            self.skipTest("gameplay scene did not initialize crates/player")

        crates.clear()
        crates.append(
            CrateState(
                crate_id=0,
                type1=1,
                type2=0,
                x=player.x + 6.0,
                y=player.y + 6.0,
                health=12.0,
                max_health=12.0,
            ),
        )

        manager.update(0.025)

        self.assertEqual(context.runtime.crates_collected_by_player, 1)
        self.assertEqual(context.runtime.crates_alive, 0)

    def test_gameplay_runtime_reports_current_weapon_ammo_snapshot(self) -> None:
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

        player.grant_weapon(1)
        player.current_weapon = 1
        player.cash = 321
        player.shield = 4
        player.target_system_enabled = True
        gained = grant_bullet_ammo(player, 0, 37)
        self.assertEqual(gained, 37)
        gained = grant_bullet_ammo(player, 7, 4000)
        self.assertEqual(gained, 3000)

        manager.update(0.025)
        self.assertEqual(context.runtime.player_current_ammo_type_index, 0)
        self.assertEqual(context.runtime.player_current_ammo_units, 37)
        self.assertEqual(context.runtime.player_current_ammo_capacity, 300)
        self.assertEqual(context.runtime.player_cash, 321)
        self.assertEqual(context.runtime.player_shield, 4)
        self.assertTrue(context.runtime.player_target_system_enabled)
        self.assertEqual(
            context.runtime.player_ammo_pools,
            (37, 0, 0, 0, 0, 0, 0, 3000, 0),
        )
        self.assertEqual(
            context.runtime.player_ammo_capacities,
            (300, 300, 300, 150, 125, 100, 100, 3000, 100),
        )

        player.current_weapon = 0
        manager.update(0.025)
        self.assertEqual(context.runtime.player_current_ammo_type_index, -1)
        self.assertEqual(context.runtime.player_current_ammo_units, 0)
        self.assertEqual(context.runtime.player_current_ammo_capacity, 0)
        self.assertEqual(
            context.runtime.player_ammo_pools,
            (37, 0, 0, 0, 0, 0, 0, 3000, 0),
        )


if __name__ == "__main__":
    unittest.main()

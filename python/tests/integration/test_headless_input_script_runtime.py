from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.app import GameApplication
from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.paths import GamePaths
from ultimatetk.systems import combat
from ultimatetk.systems.player_control import grant_bullet_ammo


class HeadlessInputScriptRuntimeTests(unittest.TestCase):
    def test_scripted_turn_changes_player_angle(self) -> None:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.6,
            input_script="5:+TURN_LEFT;11:-TURN_LEFT",
        )
        app = GameApplication.create(config=config, paths=paths)

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertNotEqual(app.context.runtime.player_angle_degrees, 0)

    def test_scripted_shoot_increments_shot_counter(self) -> None:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.8,
            input_script="5:+SHOOT;40:-SHOOT",
        )
        app = GameApplication.create(config=config, paths=paths)

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertGreater(app.context.runtime.player_shots_fired_total, 0)
        self.assertGreaterEqual(app.context.runtime.enemies_total, app.context.runtime.enemies_alive)

    def test_scripted_shop_open_and_buy_attempt_sets_shop_runtime(self) -> None:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.0,
            input_script="15:+SHOP;16:+SHOOT;17:+SHOOT;18:+SHOOT;19:+SHOOT;20:+SHOOT",
        )
        app = GameApplication.create(config=config, paths=paths)

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertTrue(app.context.runtime.shop_active)
        self.assertEqual(app.context.runtime.shop_last_action, "buy")
        self.assertEqual(app.context.runtime.shop_last_category, "weapon")
        self.assertFalse(app.context.runtime.shop_last_success)
        self.assertEqual(app.context.runtime.shop_last_reason, "NO CASH")

    def test_scripted_mine_and_c4_update_explosive_runtime(self) -> None:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=2.5,
            input_script="20:+SHOOT;35:-SHOOT;40:WEAPON=9;55:+SHOOT;70:-SHOOT",
        )
        app = GameApplication.create(config=config, paths=paths)

        app.scene_manager.update(0.025)
        app.scene_manager.update(0.025)
        if app.scene_manager.current_scene_name != "gameplay":
            self.skipTest("failed to enter gameplay scene")

        gameplay_scene = app.scene_manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        if player is None or enemies is None:
            self.skipTest("gameplay scene did not initialize combat state")

        enemies.clear()
        player.grant_weapon(11)
        player.grant_weapon(9)
        self.assertGreater(grant_bullet_ammo(player, 8, 2), 0)
        self.assertGreater(grant_bullet_ammo(player, 6, 2), 0)
        player.current_weapon = 11
        player.load_count = player.current_weapon_profile.loading_time

        with patch.object(combat, "PLAYER_C4_FUSE_TICKS", 12):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertGreaterEqual(app.context.runtime.player_shots_fired_total, 2)
        self.assertGreaterEqual(app.context.runtime.player_explosive_detonations_total, 1)
        self.assertGreaterEqual(app.context.runtime.player_mines_active, 1)
        self.assertEqual(app.context.runtime.player_c4_active, 0)
        self.assertGreaterEqual(app.context.runtime.player_explosives_active, 1)


if __name__ == "__main__":
    unittest.main()

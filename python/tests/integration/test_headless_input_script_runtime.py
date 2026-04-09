from __future__ import annotations

from dataclasses import replace
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
from ultimatetk.formats.lev import Block
from ultimatetk.rendering.constants import FLOOR_BLOCK_TYPE, WALL_BLOCK_TYPE
from ultimatetk.systems import combat
from ultimatetk.systems.player_control import grant_bullet_ammo


class HeadlessInputScriptRuntimeTests(unittest.TestCase):
    def _run_scripted_c4_crate_scenario(
        self,
        *,
        wall_tiles: set[tuple[int, int]],
    ) -> tuple[int, int, int]:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.6,
            input_script="20:+SHOOT;35:-SHOOT",
        )
        app = GameApplication.create(config=config, paths=paths)

        app.scene_manager.update(0.025)
        app.scene_manager.update(0.025)
        if app.scene_manager.current_scene_name != "gameplay":
            self.skipTest("failed to enter gameplay scene")

        gameplay_scene = app.scene_manager._current_scene  # type: ignore[attr-defined]
        level = getattr(gameplay_scene, "_level", None)
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        enemy_projectiles = getattr(gameplay_scene, "_enemy_projectiles", None)
        player_explosives = getattr(gameplay_scene, "_player_explosives", None)
        if (
            level is None
            or player is None
            or enemies is None
            or crates is None
            or enemy_projectiles is None
            or player_explosives is None
        ):
            self.skipTest("gameplay scene did not initialize combat state")

        blocks = list(level.blocks)

        def set_block(tile_x: int, tile_y: int, block_type: int) -> None:
            if tile_x < 0 or tile_x >= level.level_x_size:
                return
            if tile_y < 0 or tile_y >= level.level_y_size:
                return
            index = tile_y * level.level_x_size + tile_x
            old = blocks[index]
            blocks[index] = Block(type=block_type, num=old.num, shadow=old.shadow)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                set_block(tile_x, tile_y, FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            set_block(tile_x, tile_y, WALL_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        crates.append(
            combat.CrateState(
                crate_id=0,
                type1=0,
                type2=0,
                x=47.0,
                y=97.0,
                health=12.0,
                max_health=12.0,
            ),
        )

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False
        player.grant_weapon(9)
        for bullet_type in range(len(player.bullets)):
            player.bullets[bullet_type] = 0
        self.assertGreater(grant_bullet_ammo(player, 6, 1), 0)
        player.current_weapon = 9
        player.load_count = player.current_weapon_profile.loading_time

        gameplay_scene._enemy_hits_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._enemies_killed_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._crates_destroyed_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._player_explosive_detonations = 0  # type: ignore[attr-defined]

        with patch.object(combat, "PLAYER_C4_FUSE_TICKS", 10):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.crates_destroyed_by_player,
            app.context.runtime.player_explosive_detonations_total,
            app.context.runtime.player_shots_fired_total,
        )

    def _run_scripted_c4_side_leak_scenario(
        self,
        *,
        wall_tiles: set[tuple[int, int]],
        crate_health: float,
    ) -> tuple[float, bool, int, int]:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.6,
            input_script="20:+SHOOT;35:-SHOOT",
        )
        app = GameApplication.create(config=config, paths=paths)

        app.scene_manager.update(0.025)
        app.scene_manager.update(0.025)
        if app.scene_manager.current_scene_name != "gameplay":
            self.skipTest("failed to enter gameplay scene")

        gameplay_scene = app.scene_manager._current_scene  # type: ignore[attr-defined]
        level = getattr(gameplay_scene, "_level", None)
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        enemy_projectiles = getattr(gameplay_scene, "_enemy_projectiles", None)
        player_explosives = getattr(gameplay_scene, "_player_explosives", None)
        if (
            level is None
            or player is None
            or enemies is None
            or crates is None
            or enemy_projectiles is None
            or player_explosives is None
        ):
            self.skipTest("gameplay scene did not initialize combat state")

        blocks = list(level.blocks)

        def set_block(tile_x: int, tile_y: int, block_type: int) -> None:
            if tile_x < 0 or tile_x >= level.level_x_size:
                return
            if tile_y < 0 or tile_y >= level.level_y_size:
                return
            index = tile_y * level.level_x_size + tile_x
            old = blocks[index]
            blocks[index] = Block(type=block_type, num=old.num, shadow=old.shadow)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                set_block(tile_x, tile_y, FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            set_block(tile_x, tile_y, WALL_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        crates.append(
            combat.CrateState(
                crate_id=0,
                type1=0,
                type2=0,
                x=47.0,
                y=97.0,
                health=crate_health,
                max_health=crate_health,
            ),
        )

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False
        player.grant_weapon(9)
        for bullet_type in range(len(player.bullets)):
            player.bullets[bullet_type] = 0
        self.assertGreater(grant_bullet_ammo(player, 6, 1), 0)
        player.current_weapon = 9
        player.load_count = player.current_weapon_profile.loading_time

        gameplay_scene._enemy_hits_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._enemies_killed_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._crates_destroyed_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._player_explosive_detonations = 0  # type: ignore[attr-defined]

        with patch.object(combat, "PLAYER_C4_FUSE_TICKS", 10):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        crate = crates[0]
        return (
            crate.health,
            crate.alive,
            app.context.runtime.crates_destroyed_by_player,
            app.context.runtime.player_shots_fired_total,
        )

    def _run_scripted_mine_corridor_scenario(
        self,
        *,
        wall_tiles: set[tuple[int, int]],
        enemy_x: float = 40.0,
        enemy_y: float = 50.0,
        crate_x: float = 51.0,
        crate_y: float = 62.0,
        crate_health: float = 12.0,
    ) -> tuple[float, bool, int, int, int, int]:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.8,
            input_script="20:+SHOOT;35:-SHOOT",
        )
        app = GameApplication.create(config=config, paths=paths)

        app.scene_manager.update(0.025)
        app.scene_manager.update(0.025)
        if app.scene_manager.current_scene_name != "gameplay":
            self.skipTest("failed to enter gameplay scene")

        gameplay_scene = app.scene_manager._current_scene  # type: ignore[attr-defined]
        level = getattr(gameplay_scene, "_level", None)
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        enemy_projectiles = getattr(gameplay_scene, "_enemy_projectiles", None)
        player_explosives = getattr(gameplay_scene, "_player_explosives", None)
        if (
            level is None
            or player is None
            or enemies is None
            or crates is None
            or enemy_projectiles is None
            or player_explosives is None
        ):
            self.skipTest("gameplay scene did not initialize combat state")

        blocks = list(level.blocks)

        def set_block(tile_x: int, tile_y: int, block_type: int) -> None:
            if tile_x < 0 or tile_x >= level.level_x_size:
                return
            if tile_y < 0 or tile_y >= level.level_y_size:
                return
            index = tile_y * level.level_x_size + tile_x
            old = blocks[index]
            blocks[index] = Block(type=block_type, num=old.num, shadow=old.shadow)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                set_block(tile_x, tile_y, FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            set_block(tile_x, tile_y, WALL_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=0,
                x=enemy_x,
                y=enemy_y,
                health=18.0,
                max_health=18.0,
                angle=180,
                target_angle=180,
                load_count=0,
            ),
        )
        crates.append(
            combat.CrateState(
                crate_id=0,
                type1=0,
                type2=0,
                x=crate_x,
                y=crate_y,
                health=crate_health,
                max_health=crate_health,
            ),
        )

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False
        player.grant_weapon(11)
        for bullet_type in range(len(player.bullets)):
            player.bullets[bullet_type] = 0
        self.assertGreater(grant_bullet_ammo(player, 8, 1), 0)
        player.current_weapon = 11
        player.load_count = player.current_weapon_profile.loading_time

        gameplay_scene._enemy_hits_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._enemies_killed_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._crates_destroyed_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._player_explosive_detonations = 0  # type: ignore[attr-defined]

        with patch.object(combat, "PLAYER_MINE_SLEEP_TICKS", 2), patch.object(
            combat,
            "enemy_speed_for_type",
            return_value=0.0,
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        crate = crates[0]
        return (
            crate.health,
            crate.alive,
            app.context.runtime.crates_destroyed_by_player,
            app.context.runtime.player_explosive_detonations_total,
            app.context.runtime.player_shots_fired_total,
            app.context.runtime.enemies_killed_by_player,
        )

    def _run_scripted_enemy_grenade_obstruction_scenario(
        self,
        *,
        wall_tiles: set[tuple[int, int]],
    ) -> tuple[int, int, float]:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.7,
        )
        app = GameApplication.create(config=config, paths=paths)

        app.scene_manager.update(0.025)
        app.scene_manager.update(0.025)
        if app.scene_manager.current_scene_name != "gameplay":
            self.skipTest("failed to enter gameplay scene")

        gameplay_scene = app.scene_manager._current_scene  # type: ignore[attr-defined]
        level = getattr(gameplay_scene, "_level", None)
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        enemy_projectiles = getattr(gameplay_scene, "_enemy_projectiles", None)
        player_explosives = getattr(gameplay_scene, "_player_explosives", None)
        if (
            level is None
            or player is None
            or enemies is None
            or crates is None
            or enemy_projectiles is None
            or player_explosives is None
        ):
            self.skipTest("gameplay scene did not initialize combat state")

        blocks = list(level.blocks)

        def set_block(tile_x: int, tile_y: int, block_type: int) -> None:
            if tile_x < 0 or tile_x >= level.level_x_size:
                return
            if tile_y < 0 or tile_y >= level.level_y_size:
                return
            index = tile_y * level.level_x_size + tile_x
            old = blocks[index]
            blocks[index] = Block(type=block_type, num=old.num, shadow=old.shadow)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                set_block(tile_x, tile_y, FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            set_block(tile_x, tile_y, WALL_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=4,
                x=40.0,
                y=80.0,
                health=40.0,
                max_health=40.0,
                angle=180,
                target_angle=180,
                load_count=30,
            ),
        )

        player.x = 40.0
        player.y = 68.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False
        player.hits_taken_total = 0
        player.damage_taken_total = 0.0

        gameplay_scene._enemy_hits_on_player = 0  # type: ignore[attr-defined]
        gameplay_scene._enemy_damage_to_player = 0.0  # type: ignore[attr-defined]
        gameplay_scene._enemy_shots_fired = 0  # type: ignore[attr-defined]

        with patch.object(combat, "enemy_speed_for_type", return_value=0.0):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.enemy_shots_fired_total,
            app.context.runtime.enemy_hits_total,
            app.context.runtime.player_damage_taken_total,
        )

    def _run_scripted_enemy_los_corner_graze_scenario(
        self,
        *,
        wall_tiles: set[tuple[int, int]],
        enemy_type_index: int = 0,
        enemy_x: float = 6.0,
        enemy_y: float = 6.0,
        enemy_angle: int = 34,
        enemy_load_count: int = 10,
        player_x: float = 54.0,
        player_y: float = 76.0,
    ) -> tuple[int, int, float]:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.6,
        )
        app = GameApplication.create(config=config, paths=paths)

        app.scene_manager.update(0.025)
        app.scene_manager.update(0.025)
        if app.scene_manager.current_scene_name != "gameplay":
            self.skipTest("failed to enter gameplay scene")

        gameplay_scene = app.scene_manager._current_scene  # type: ignore[attr-defined]
        level = getattr(gameplay_scene, "_level", None)
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        enemy_projectiles = getattr(gameplay_scene, "_enemy_projectiles", None)
        player_explosives = getattr(gameplay_scene, "_player_explosives", None)
        if (
            level is None
            or player is None
            or enemies is None
            or crates is None
            or enemy_projectiles is None
            or player_explosives is None
        ):
            self.skipTest("gameplay scene did not initialize combat state")

        blocks = list(level.blocks)

        def set_block(tile_x: int, tile_y: int, block_type: int) -> None:
            if tile_x < 0 or tile_x >= level.level_x_size:
                return
            if tile_y < 0 or tile_y >= level.level_y_size:
                return
            index = tile_y * level.level_x_size + tile_x
            old = blocks[index]
            blocks[index] = Block(type=block_type, num=old.num, shadow=old.shadow)

        for tile_y in range(0, 6):
            for tile_x in range(0, 6):
                set_block(tile_x, tile_y, FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            set_block(tile_x, tile_y, WALL_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=enemy_type_index,
                x=enemy_x,
                y=enemy_y,
                health=18.0,
                max_health=18.0,
                angle=enemy_angle,
                target_angle=enemy_angle,
                load_count=enemy_load_count,
            ),
        )

        player.x = player_x
        player.y = player_y
        player.angle = 0
        player.health = player.max_health
        player.dead = False
        player.hits_taken_total = 0
        player.damage_taken_total = 0.0

        gameplay_scene._enemy_hits_on_player = 0  # type: ignore[attr-defined]
        gameplay_scene._enemy_damage_to_player = 0.0  # type: ignore[attr-defined]
        gameplay_scene._enemy_shots_fired = 0  # type: ignore[attr-defined]

        with patch.object(combat, "enemy_speed_for_type", return_value=0.0):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.enemy_shots_fired_total,
            app.context.runtime.enemy_hits_total,
            app.context.runtime.player_damage_taken_total,
        )

    def _run_scripted_player_shot_corner_graze_scenario(
        self,
        *,
        wall_tiles: set[tuple[int, int]],
    ) -> tuple[int, int, int]:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.8,
            input_script="20:+SHOOT;24:-SHOOT",
        )
        app = GameApplication.create(config=config, paths=paths)

        app.scene_manager.update(0.025)
        app.scene_manager.update(0.025)
        if app.scene_manager.current_scene_name != "gameplay":
            self.skipTest("failed to enter gameplay scene")

        gameplay_scene = app.scene_manager._current_scene  # type: ignore[attr-defined]
        level = getattr(gameplay_scene, "_level", None)
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        enemy_projectiles = getattr(gameplay_scene, "_enemy_projectiles", None)
        player_explosives = getattr(gameplay_scene, "_player_explosives", None)
        if (
            level is None
            or player is None
            or enemies is None
            or crates is None
            or enemy_projectiles is None
            or player_explosives is None
        ):
            self.skipTest("gameplay scene did not initialize combat state")

        blocks = list(level.blocks)

        def set_block(tile_x: int, tile_y: int, block_type: int) -> None:
            if tile_x < 0 or tile_x >= level.level_x_size:
                return
            if tile_y < 0 or tile_y >= level.level_y_size:
                return
            index = tile_y * level.level_x_size + tile_x
            old = blocks[index]
            blocks[index] = Block(type=block_type, num=old.num, shadow=old.shadow)

        for tile_y in range(0, 6):
            for tile_x in range(0, 6):
                set_block(tile_x, tile_y, FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            set_block(tile_x, tile_y, WALL_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=0,
                x=56.0,
                y=0.0,
                health=5.0,
                max_health=5.0,
                angle=180,
                target_angle=180,
                load_count=0,
            ),
        )

        player.x = 6.0
        player.y = 46.0
        player.angle = 136
        player.health = player.max_health
        player.dead = False
        player.grant_weapon(1)
        for bullet_type in range(len(player.bullets)):
            player.bullets[bullet_type] = 0
        self.assertGreater(grant_bullet_ammo(player, 0, 1), 0)
        player.current_weapon = 1
        player.load_count = player.current_weapon_profile.loading_time

        gameplay_scene._enemy_hits_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._enemies_killed_by_player = 0  # type: ignore[attr-defined]

        with patch.object(combat, "enemy_speed_for_type", return_value=0.0), patch.object(
            combat,
            "_can_enemy_fire",
            return_value=False,
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.player_shots_fired_total,
            app.context.runtime.player_hits_total,
            app.context.runtime.enemies_killed_by_player,
        )

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

    def test_scripted_c4_corner_obstruction_blocks_crate_damage(self) -> None:
        open_destroyed, open_detonations, open_shots = self._run_scripted_c4_crate_scenario(wall_tiles=set())
        blocked_destroyed, blocked_detonations, blocked_shots = self._run_scripted_c4_crate_scenario(
            wall_tiles={(2, 4), (2, 5), (3, 4)},
        )

        self.assertGreaterEqual(open_shots, 1)
        self.assertGreaterEqual(blocked_shots, 1)
        self.assertGreaterEqual(open_detonations, 1)
        self.assertGreaterEqual(blocked_detonations, 1)
        self.assertGreaterEqual(open_destroyed, 1)
        self.assertEqual(blocked_destroyed, 0)

    def test_scripted_c4_side_wall_has_damped_leakage(self) -> None:
        open_hp, open_alive, open_destroyed, open_shots = self._run_scripted_c4_side_leak_scenario(
            wall_tiles=set(),
            crate_health=12.0,
        )
        side_hp, side_alive, side_destroyed, side_shots = self._run_scripted_c4_side_leak_scenario(
            wall_tiles={(3, 4)},
            crate_health=12.0,
        )
        blocked_hp, blocked_alive, blocked_destroyed, blocked_shots = self._run_scripted_c4_side_leak_scenario(
            wall_tiles={(2, 4), (2, 5), (3, 4)},
            crate_health=12.0,
        )

        self.assertGreaterEqual(open_shots, 1)
        self.assertGreaterEqual(side_shots, 1)
        self.assertGreaterEqual(blocked_shots, 1)
        self.assertFalse(open_alive)
        self.assertEqual(open_hp, 0.0)
        self.assertGreaterEqual(open_destroyed, 1)

        self.assertTrue(side_alive)
        self.assertEqual(side_destroyed, 0)
        self.assertGreater(side_hp, 0.0)
        self.assertLess(side_hp, 12.0)

        self.assertTrue(blocked_alive)
        self.assertEqual(blocked_destroyed, 0)
        self.assertEqual(blocked_hp, 12.0)

    def test_scripted_mine_corridor_obstruction_blocks_crate_damage(self) -> None:
        open_hp, open_alive, open_destroyed, open_detonations, open_shots, open_kills = (
            self._run_scripted_mine_corridor_scenario(
                wall_tiles=set(),
            )
        )
        blocked_hp, blocked_alive, blocked_destroyed, blocked_detonations, blocked_shots, blocked_kills = (
            self._run_scripted_mine_corridor_scenario(wall_tiles={(2, 3)})
        )

        self.assertGreaterEqual(open_shots, 1)
        self.assertGreaterEqual(blocked_shots, 1)
        self.assertGreaterEqual(open_detonations, 1)
        self.assertGreaterEqual(blocked_detonations, 1)
        self.assertFalse(open_alive)
        self.assertEqual(open_hp, 0.0)
        self.assertGreaterEqual(open_destroyed, 1)
        self.assertTrue(blocked_alive)
        self.assertEqual(blocked_hp, 12.0)
        self.assertEqual(blocked_destroyed, 0)
        self.assertGreaterEqual(open_kills, 1)
        self.assertEqual(blocked_kills, 0)

    def test_scripted_c4_diagonal_and_one_tile_choke_microcases(self) -> None:
        open_hp, open_alive, open_destroyed, open_shots = self._run_scripted_c4_side_leak_scenario(
            wall_tiles=set(),
            crate_health=12.0,
        )
        diagonal_hp, diagonal_alive, diagonal_destroyed, diagonal_shots = self._run_scripted_c4_side_leak_scenario(
            wall_tiles={(3, 5)},
            crate_health=12.0,
        )
        choke_hp, choke_alive, choke_destroyed, choke_shots = self._run_scripted_c4_side_leak_scenario(
            wall_tiles={(2, 4), (3, 5)},
            crate_health=12.0,
        )

        self.assertGreaterEqual(open_shots, 1)
        self.assertGreaterEqual(diagonal_shots, 1)
        self.assertGreaterEqual(choke_shots, 1)
        self.assertFalse(open_alive)
        self.assertEqual(open_hp, 0.0)
        self.assertGreaterEqual(open_destroyed, 1)

        self.assertTrue(diagonal_alive)
        self.assertGreater(diagonal_hp, 0.0)
        self.assertLess(diagonal_hp, 12.0)
        self.assertEqual(diagonal_destroyed, 0)

        self.assertTrue(choke_alive)
        self.assertGreaterEqual(choke_hp, diagonal_hp)
        self.assertEqual(choke_destroyed, 0)

    def test_scripted_mine_diagonal_and_one_tile_choke_microcases(self) -> None:
        open_hp, open_alive, open_destroyed, open_detonations, open_shots, open_kills = (
            self._run_scripted_mine_corridor_scenario(wall_tiles=set())
        )
        diagonal_hp, diagonal_alive, diagonal_destroyed, diagonal_detonations, diagonal_shots, diagonal_kills = (
            self._run_scripted_mine_corridor_scenario(wall_tiles={(3, 3)})
        )
        choke_hp, choke_alive, choke_destroyed, choke_detonations, choke_shots, choke_kills = (
            self._run_scripted_mine_corridor_scenario(wall_tiles={(2, 2)})
        )

        self.assertGreaterEqual(open_shots, 1)
        self.assertGreaterEqual(diagonal_shots, 1)
        self.assertGreaterEqual(choke_shots, 1)
        self.assertGreaterEqual(open_detonations, 1)
        self.assertGreaterEqual(diagonal_detonations, 1)
        self.assertGreaterEqual(choke_detonations, 1)
        self.assertFalse(open_alive)
        self.assertEqual(open_hp, 0.0)

        self.assertGreaterEqual(diagonal_hp, open_hp)
        self.assertLessEqual(diagonal_destroyed, open_destroyed)
        self.assertLessEqual(diagonal_kills, open_kills)

        self.assertGreaterEqual(choke_hp, diagonal_hp)
        self.assertLessEqual(choke_destroyed, diagonal_destroyed)
        self.assertLessEqual(choke_kills, diagonal_kills)

        self.assertTrue(
            diagonal_destroyed < open_destroyed or diagonal_kills < open_kills,
        )
        self.assertTrue(
            choke_destroyed < open_destroyed or choke_kills < open_kills,
        )

    def test_scripted_enemy_grenade_obstruction_partial_vs_blocked(self) -> None:
        partial_shots, partial_hits, partial_damage = self._run_scripted_enemy_grenade_obstruction_scenario(
            wall_tiles={(2, 3)},
        )
        blocked_shots, blocked_hits, blocked_damage = self._run_scripted_enemy_grenade_obstruction_scenario(
            wall_tiles={(2, 3), (2, 4)},
        )

        self.assertGreaterEqual(partial_shots, 1)
        self.assertGreaterEqual(partial_hits, 1)
        self.assertGreater(partial_damage, 0.0)
        self.assertLess(partial_damage, 20.0)

        self.assertEqual(blocked_shots, 0)
        self.assertEqual(blocked_hits, 0)
        self.assertEqual(blocked_damage, 0.0)

    def test_scripted_enemy_los_corner_graze_open_vs_blocked(self) -> None:
        open_shots, open_hits, open_damage = self._run_scripted_enemy_los_corner_graze_scenario(
            wall_tiles=set(),
        )
        blocked_shots, blocked_hits, blocked_damage = self._run_scripted_enemy_los_corner_graze_scenario(
            wall_tiles={(3, 3)},
        )

        self.assertGreaterEqual(open_shots, 1)
        self.assertGreaterEqual(open_hits, 1)
        self.assertGreater(open_damage, 0.0)

        self.assertEqual(blocked_shots, 0)
        self.assertEqual(blocked_hits, 0)
        self.assertEqual(blocked_damage, 0.0)

    def test_scripted_enemy_direct_shot_corner_graze_open_vs_blocked(self) -> None:
        open_shots, open_hits, open_damage = self._run_scripted_enemy_los_corner_graze_scenario(
            wall_tiles=set(),
            enemy_type_index=5,
            enemy_x=28.0,
            enemy_y=10.0,
            enemy_angle=352,
            enemy_load_count=10,
            player_x=24.0,
            player_y=38.0,
        )
        blocked_shots, blocked_hits, blocked_damage = self._run_scripted_enemy_los_corner_graze_scenario(
            wall_tiles={(1, 1)},
            enemy_type_index=5,
            enemy_x=28.0,
            enemy_y=10.0,
            enemy_angle=352,
            enemy_load_count=10,
            player_x=24.0,
            player_y=38.0,
        )

        self.assertGreaterEqual(open_shots, 1)
        self.assertGreaterEqual(open_hits, 1)
        self.assertGreater(open_damage, 0.0)

        self.assertGreaterEqual(blocked_shots, 1)
        self.assertEqual(blocked_hits, 0)
        self.assertEqual(blocked_damage, 0.0)

    def test_scripted_enemy_projectile_corner_graze_open_vs_blocked(self) -> None:
        open_shots, open_hits, open_damage = self._run_scripted_enemy_los_corner_graze_scenario(
            wall_tiles=set(),
            enemy_type_index=0,
            enemy_x=0.0,
            enemy_y=0.0,
            enemy_angle=0,
            enemy_load_count=10,
            player_x=8.0,
            player_y=38.0,
        )
        blocked_shots, blocked_hits, blocked_damage = self._run_scripted_enemy_los_corner_graze_scenario(
            wall_tiles={(1, 1)},
            enemy_type_index=0,
            enemy_x=0.0,
            enemy_y=0.0,
            enemy_angle=0,
            enemy_load_count=10,
            player_x=8.0,
            player_y=38.0,
        )

        self.assertGreaterEqual(open_shots, 1)
        self.assertGreaterEqual(open_hits, 1)
        self.assertGreater(open_damage, 0.0)

        self.assertGreaterEqual(blocked_shots, 1)
        self.assertEqual(blocked_hits, 0)
        self.assertEqual(blocked_damage, 0.0)

    def test_scripted_player_shot_corner_graze_open_vs_blocked(self) -> None:
        open_shots, open_hits, open_kills = self._run_scripted_player_shot_corner_graze_scenario(
            wall_tiles=set(),
        )
        blocked_shots, blocked_hits, blocked_kills = self._run_scripted_player_shot_corner_graze_scenario(
            wall_tiles={(1, 1)},
        )

        self.assertGreaterEqual(open_shots, 1)
        self.assertGreaterEqual(blocked_shots, 1)
        self.assertGreaterEqual(open_hits, 1)
        self.assertGreaterEqual(open_kills, 1)

        self.assertEqual(blocked_hits, 0)
        self.assertEqual(blocked_kills, 0)


if __name__ == "__main__":
    unittest.main()

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
import ultimatetk.systems.gameplay_scene as gameplay_scene_module
from ultimatetk.systems.player_control import ShotEvent, bullet_capacity_units_for_type, grant_bullet_ammo


class HeadlessInputScriptRuntimeTests(unittest.TestCase):
    def _create_app_or_skip(self, config: RuntimeConfig) -> GameApplication:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")
        return GameApplication.create(config=config, paths=paths)

    def _enter_gameplay_or_skip(self, app: GameApplication) -> object:
        app.scene_manager.update(0.025)
        app.scene_manager.update(0.025)
        if app.scene_manager.current_scene_name != "gameplay":
            self.skipTest("failed to enter gameplay scene")
        return app.scene_manager._current_scene  # type: ignore[attr-defined]

    def _extract_combat_state_or_skip(
        self,
        gameplay_scene: object,
    ) -> tuple[object, object, object, object, object, object]:
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
        return level, player, enemies, crates, enemy_projectiles, player_explosives

    @staticmethod
    def _set_block(blocks: list[Block], level: object, *, tile_x: int, tile_y: int, block_type: int) -> None:
        level_x_size = level.level_x_size
        level_y_size = level.level_y_size
        if tile_x < 0 or tile_x >= level_x_size:
            return
        if tile_y < 0 or tile_y >= level_y_size:
            return
        index = tile_y * level_x_size + tile_x
        old = blocks[index]
        blocks[index] = Block(type=block_type, num=old.num, shadow=old.shadow)

    def _run_scripted_shield_energy_scenario(
        self,
        *,
        sell_after_collect: bool,
    ) -> tuple[int, int, int, str, str, bool]:
        script_parts = [
            "20:+SHOP",
            "26:+DOWN",
            "32:+DOWN",
            "38:+SHOOT",
            "44:+SHOP",
            "50:+UP",
            "82:-UP",
        ]
        if sell_after_collect:
            script_parts.extend(
                (
                    "100:+SHOP",
                    "106:+DOWN",
                    "112:+DOWN",
                    "118:+NEXT",
                    "140:QUIT",
                ),
            )
        else:
            script_parts.append("96:QUIT")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=3.8,
            input_script=";".join(script_parts),
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 9):
            for tile_x in range(1, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        crates.append(
            combat.CrateState(
                crate_id=0,
                type1=2,
                type2=0,
                x=47.0,
                y=72.0,
                health=12.0,
                max_health=12.0,
            ),
        )

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.max_health = 100.0
        player.health = 95.0
        player.cash = 1200
        player.shield = 0
        player.dead = False

        gameplay_scene._crates_collected_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._shop_last_transaction = None  # type: ignore[attr-defined]

        exit_code = app.run()
        self.assertEqual(exit_code, 0)

        return (
            app.context.runtime.player_health,
            app.context.runtime.player_shield,
            app.context.runtime.crates_collected_by_player,
            app.context.runtime.shop_last_action,
            app.context.runtime.shop_last_category,
            app.context.runtime.shop_last_success,
        )

    def _run_scripted_crate_collect_destroy_mix_scenario(self) -> tuple[int, int, int, int, bool]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.25,
            input_script="8:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.max_health = 100.0
        player.health = 70.0
        player.dead = False
        player.weapons[1] = False

        crates.append(
            combat.CrateState(
                crate_id=0,
                type1=2,
                type2=0,
                x=player.x + 6.0,
                y=player.y + 6.0,
                health=12.0,
                max_health=12.0,
            ),
        )
        crates.append(
            combat.CrateState(
                crate_id=1,
                type1=0,
                type2=0,
                x=48.0,
                y=84.0,
                health=12.0,
                max_health=12.0,
            ),
        )
        player.pending_shots.append(
            ShotEvent(
                origin_x=54.0,
                origin_y=64.0,
                angle=0,
                max_distance=170,
                weapon_slot=7,
                impact_x=54,
                impact_y=130,
            ),
        )

        gameplay_scene._crates_collected_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._crates_destroyed_by_player = 0  # type: ignore[attr-defined]

        exit_code = app.run()
        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.crates_collected_by_player,
            app.context.runtime.crates_destroyed_by_player,
            app.context.runtime.crates_alive,
            app.context.runtime.player_health,
            player.weapons[1],
        )

    def _run_scripted_c4_crate_scenario(
        self,
        *,
        wall_tiles: set[tuple[int, int]],
    ) -> tuple[int, int, int]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.6,
            input_script="20:+SHOOT;35:-SHOOT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=WALL_BLOCK_TYPE)

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
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.6,
            input_script="20:+SHOOT;35:-SHOOT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=WALL_BLOCK_TYPE)

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
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.8,
            input_script="20:+SHOOT;35:-SHOOT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=WALL_BLOCK_TYPE)

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
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.7,
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=WALL_BLOCK_TYPE)

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

    def _run_scripted_enemy_explosive_pressure_scenario(
        self,
        *,
        pressure_trigger_ratio: float,
    ) -> tuple[float, float, float, float, int]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.9,
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

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
                y=120.0,
                health=40.0,
                max_health=40.0,
                angle=180,
                target_angle=180,
                load_count=30,
            ),
        )

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False
        player.hits_taken_total = 0
        player.damage_taken_total = 0.0

        start_x = enemies[0].x
        start_y = enemies[0].y

        with patch.object(combat, "enemy_speed_for_type", return_value=2.0), patch.object(
            combat,
            "ENEMY_POST_SHOT_PRESSURE_TRIGGER_DISTANCE_RATIO",
            pressure_trigger_ratio,
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            start_x,
            start_y,
            enemies[0].x,
            enemies[0].y,
            app.context.runtime.enemy_shots_fired_total,
        )

    def _run_scripted_enemy_lost_sight_chase_scenario(
        self,
        *,
        prior_seen: bool,
    ) -> tuple[float, float, int, bool]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.18,
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 9):
            for tile_x in range(1, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)
        self._set_block(blocks, level, tile_x=2, tile_y=3, block_type=WALL_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=0,
                x=40.0,
                y=80.0,
                health=18.0,
                max_health=18.0,
                angle=180,
                target_angle=180,
                sees_player=prior_seen,
            ),
        )

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False

        start_y = enemies[0].y
        with patch.object(combat, "enemy_speed_for_type", return_value=2.0):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            start_y,
            enemies[0].y,
            enemies[0].chase_ticks,
            enemies[0].sees_player,
        )

    def _run_scripted_enemy_patrol_burst_scenario(
        self,
        *,
        patrol_roll_value: int,
    ) -> tuple[float, float, float, float, int]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.35,
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 16):
            for tile_x in range(0, 16):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=0,
                x=80.0,
                y=80.0,
                health=18.0,
                max_health=18.0,
                angle=0,
                target_angle=0,
                walk_ticks=0,
                load_count=0,
            ),
        )

        player.x = 280.0
        player.y = 280.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False

        start_x = enemies[0].x
        start_y = enemies[0].y
        with patch.object(combat, "enemy_speed_for_type", return_value=2.0), patch.object(
            combat,
            "_enemy_next_patrol_roll",
            return_value=patrol_roll_value,
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            start_x,
            start_y,
            enemies[0].x,
            enemies[0].y,
            enemies[0].walk_ticks,
        )

    def _run_scripted_enemy_patrol_turn_lock_scenario(self) -> tuple[int, int, int]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.08,
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 20):
            for tile_x in range(0, 20):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=0,
                x=160.0,
                y=160.0,
                health=18.0,
                max_health=18.0,
                angle=0,
                target_angle=90,
                walk_ticks=0,
                load_count=0,
            ),
        )

        player.x = 0.0
        player.y = 0.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False

        with patch.object(combat, "enemy_speed_for_type", return_value=2.0), patch.object(
            combat,
            "_enemy_next_patrol_roll",
            return_value=1,
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (enemies[0].angle, enemies[0].target_angle, enemies[0].walk_ticks)

    def _run_scripted_enemy_los_trace_step_scenario(self) -> list[int]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.08,
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 12):
            for tile_x in range(0, 12):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=0,
                x=40.0,
                y=120.0,
                health=18.0,
                max_health=18.0,
                angle=180,
                target_angle=180,
                load_count=0,
            ),
        )

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False

        steps: list[int] = []
        original_line_of_sight_clear = combat._line_of_sight_clear

        def record_line_of_sight_step(*args: object, **kwargs: object) -> bool:
            step = kwargs.get("step")
            if isinstance(step, int):
                steps.append(step)
            return original_line_of_sight_clear(*args, **kwargs)

        with patch.object(combat, "_line_of_sight_clear", side_effect=record_line_of_sight_step):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return steps

    def _run_scripted_enemy_los_corner_graze_scenario(
        self,
        *,
        wall_tiles: set[tuple[int, int]],
        enemy_type_index: int = 0,
        enemy_x: float = 6.0,
        enemy_y: float = 6.0,
        enemy_angle: int = 34,
        enemy_walk_ticks: int = 0,
        enemy_load_count: int = 10,
        player_x: float = 54.0,
        player_y: float = 76.0,
    ) -> tuple[int, int, float]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.6,
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        max_world_x = max(enemy_x, player_x)
        max_world_y = max(enemy_y, player_y)
        max_tile_x = min(level.level_x_size - 1, max(5, int(max_world_x // 20) + 2))
        max_tile_y = min(level.level_y_size - 1, max(5, int(max_world_y // 20) + 2))

        for tile_y in range(0, max_tile_y + 1):
            for tile_x in range(0, max_tile_x + 1):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=WALL_BLOCK_TYPE)

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
                walk_ticks=enemy_walk_ticks,
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
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.8,
            input_script="20:+SHOOT;24:-SHOOT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 6):
            for tile_x in range(0, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        for tile_x, tile_y in wall_tiles:
            self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=WALL_BLOCK_TYPE)

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

    def _run_scripted_enemy_strafe_fallback_scenario(
        self,
    ) -> tuple[tuple[tuple[int, bool], ...], int]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.15,
            input_script="8:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 12):
            for tile_x in range(0, 12):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        self._set_block(blocks, level, tile_x=0, tile_y=2, block_type=WALL_BLOCK_TYPE)
        self._set_block(blocks, level, tile_x=2, tile_y=0, block_type=WALL_BLOCK_TYPE)
        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=2,
                x=10.0,
                y=10.0,
                health=40.0,
                max_health=40.0,
                angle=45,
                target_angle=45,
                load_count=1,
                shoot_count=0,
            ),
        )

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False

        movement_calls: list[tuple[int, bool]] = []
        original_move_enemy = combat._move_enemy_with_collision

        def record_enemy_movement(*args: object, **kwargs: object) -> bool:
            moved = original_move_enemy(*args, **kwargs)
            angle = kwargs.get("angle")
            if isinstance(angle, int):
                movement_calls.append((angle % 360, moved))
            return moved

        with patch.object(combat, "enemy_speed_for_type", return_value=10.0), patch.object(
            combat,
            "_enemy_strafe_angle",
            return_value=45,
        ), patch.object(
            combat,
            "_can_enemy_fire",
            return_value=False,
        ), patch.object(combat, "_move_enemy_with_collision", side_effect=record_enemy_movement):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            tuple(movement_calls),
            app.context.runtime.enemy_shots_fired_total,
        )

    def _run_scripted_projectile_expiry_crate_cover_scenario(
        self,
        *,
        with_cover: bool,
    ) -> tuple[float, int, int, int, float]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.15,
            input_script="8:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 12):
            for tile_x in range(0, 12):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        cover_crate: combat.CrateState | None = None
        if with_cover:
            cover_crate = combat.CrateState(
                crate_id=0,
                type1=0,
                type2=0,
                x=28.0,
                y=64.0,
                health=12.0,
                max_health=12.0,
            )
            crates.append(cover_crate)

        player.x = 20.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False
        player.hits_taken_total = 0
        player.damage_taken_total = 0.0

        enemy_projectiles.append(
            combat.EnemyProjectile(
                owner_enemy_id=0,
                weapon_slot=5,
                x=54.0,
                y=84.0,
                vx=0.0,
                vy=0.0,
                speed=0.0,
                damage=20.0,
                remaining_ticks=1,
                radius=0,
                splash_radius=48,
            ),
        )

        gameplay_scene._enemy_hits_on_player = 0  # type: ignore[attr-defined]
        gameplay_scene._enemy_damage_to_player = 0.0  # type: ignore[attr-defined]
        gameplay_scene._enemy_shots_fired = 0  # type: ignore[attr-defined]

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.player_damage_taken_total,
            app.context.runtime.enemy_hits_total,
            app.context.runtime.enemy_projectiles_active,
            app.context.runtime.crates_collected_by_player,
            0.0 if cover_crate is None else cover_crate.health,
        )

    def _run_scripted_dead_player_projectile_telemetry_gating_scenario(
        self,
    ) -> tuple[int, float, int, int, float, bool, float]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.2,
            input_script="8:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 12):
            for tile_x in range(0, 12):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        crate = combat.CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=96.0,
            y=96.0,
            health=12.0,
            max_health=12.0,
        )
        crates.append(crate)
        enemy_projectiles.append(
            combat.EnemyProjectile(
                owner_enemy_id=0,
                weapon_slot=1,
                x=54.0,
                y=54.0,
                vx=0.0,
                vy=1.0,
                speed=8.0,
                damage=5.0,
                remaining_ticks=10,
                radius=1,
                splash_radius=0,
            ),
        )

        player.health = 0.0
        player.dead = True
        player.hits_taken_total = 0
        player.damage_taken_total = 0.0

        gameplay_scene._enemy_hits_on_player = 0  # type: ignore[attr-defined]
        gameplay_scene._enemy_damage_to_player = 0.0  # type: ignore[attr-defined]

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.enemy_hits_total,
            app.context.runtime.enemy_damage_to_player_total,
            app.context.runtime.enemy_projectiles_active,
            app.context.runtime.player_hits_taken_total,
            app.context.runtime.player_damage_taken_total,
            app.context.runtime.game_over_active,
            crate.health,
        )

    def _run_scripted_unknown_owner_projectile_retention_scenario(self) -> tuple[int, int, int, float]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.2,
            input_script="8:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 12):
            for tile_x in range(0, 12):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=7,
                type_index=0,
                x=40.0,
                y=80.0,
                health=18.0,
                max_health=18.0,
                angle=180,
                target_angle=180,
                alive=True,
            ),
        )
        enemy_projectiles.append(
            combat.EnemyProjectile(
                owner_enemy_id=99,
                weapon_slot=1,
                x=54.0,
                y=66.0,
                vx=0.0,
                vy=-1.0,
                speed=8.0,
                damage=5.0,
                remaining_ticks=10,
                radius=1,
                splash_radius=0,
            ),
        )

        player.x = 40.0
        player.y = 40.0
        player.health = player.max_health
        player.dead = False
        player.hits_taken_total = 0
        player.damage_taken_total = 0.0

        with patch.object(
            gameplay_scene_module,
            "update_enemy_behavior",
            return_value=combat.EnemyBehaviorReport(),
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.enemy_hits_total,
            app.context.runtime.player_hits_taken_total,
            app.context.runtime.enemy_projectiles_active,
            app.context.runtime.player_damage_taken_total,
        )

    def _run_scripted_dead_player_buffer_cleanup_scenario(self) -> tuple[int, int, int, int, float, bool]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.2,
            input_script="8:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 12):
            for tile_x in range(0, 12):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemy_projectiles.append(
            combat.EnemyProjectile(
                owner_enemy_id=99,
                weapon_slot=1,
                x=54.0,
                y=66.0,
                vx=0.0,
                vy=-1.0,
                speed=8.0,
                damage=5.0,
                remaining_ticks=10,
                radius=1,
                splash_radius=0,
            ),
        )
        player_explosives.append(
            combat.PlayerExplosive(
                kind="mine",
                x=120.0,
                y=120.0,
                angle=0,
                fuse_ticks=1,
                arming_ticks=0,
                radius=70,
                damage=40.0,
                falloff_exponent=1.25,
                trigger_radius=14,
            ),
        )

        player.health = 0.0
        player.dead = True
        player.hits_taken_total = 0
        player.damage_taken_total = 0.0

        gameplay_scene._enemy_hits_on_player = 0  # type: ignore[attr-defined]
        gameplay_scene._enemy_damage_to_player = 0.0  # type: ignore[attr-defined]
        gameplay_scene._player_explosive_detonations = 0  # type: ignore[attr-defined]

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.enemy_projectiles_active,
            app.context.runtime.player_explosives_active,
            app.context.runtime.player_explosive_detonations_total,
            app.context.runtime.enemy_hits_total,
            app.context.runtime.enemy_damage_to_player_total,
            app.context.runtime.game_over_active,
        )

    def _run_scripted_player_death_halts_followup_projectile_side_effects_scenario(
        self,
        *,
        lethal_first: bool = True,
    ) -> tuple[int, float, float, int, int, bool]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.2,
            input_script="8:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 12):
            for tile_x in range(0, 12):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        crate = combat.CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=96.0,
            y=96.0,
            health=12.0,
            max_health=12.0,
        )
        crates.append(crate)
        lethal_projectile = combat.EnemyProjectile(
            owner_enemy_id=1,
            weapon_slot=1,
            x=54.0,
            y=66.0,
            vx=0.0,
            vy=-1.0,
            speed=8.0,
            damage=5.0,
            remaining_ticks=10,
            radius=1,
            splash_radius=0,
        )
        crate_projectile = combat.EnemyProjectile(
            owner_enemy_id=2,
            weapon_slot=1,
            x=102.0,
            y=94.0,
            vx=0.0,
            vy=1.0,
            speed=8.0,
            damage=5.0,
            remaining_ticks=10,
            radius=1,
            splash_radius=0,
        )
        if lethal_first:
            enemy_projectiles.append(lethal_projectile)
            enemy_projectiles.append(crate_projectile)
        else:
            enemy_projectiles.append(crate_projectile)
            enemy_projectiles.append(lethal_projectile)

        player.x = 40.0
        player.y = 40.0
        player.health = 4.0
        player.dead = False
        player.hits_taken_total = 0
        player.damage_taken_total = 0.0

        with patch.object(
            gameplay_scene_module,
            "update_enemy_behavior",
            return_value=combat.EnemyBehaviorReport(),
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.enemy_hits_total,
            app.context.runtime.enemy_damage_to_player_total,
            crate.health,
            app.context.runtime.enemy_projectiles_active,
            app.context.runtime.player_hits_taken_total,
            app.context.runtime.game_over_active,
        )

    def _run_scripted_multi_enemy_strafe_stagger_scenario(
        self,
    ) -> dict[int, tuple[int, ...]]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.2,
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(0, 16):
            for tile_x in range(0, 16):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=2,
                x=40.0,
                y=80.0,
                health=40.0,
                max_health=40.0,
                angle=180,
                target_angle=180,
                load_count=0,
            ),
        )
        enemies.append(
            combat.EnemyState(
                enemy_id=1,
                type_index=2,
                x=80.0,
                y=80.0,
                health=40.0,
                max_health=40.0,
                angle=180,
                target_angle=180,
                load_count=0,
            ),
        )

        player.x = 60.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False

        movement_angles: dict[int, list[int]] = {
            0: [],
            1: [],
        }

        def record_enemy_movement(*args: object, **kwargs: object) -> bool:
            if not args:
                return True
            enemy = args[0]
            if not isinstance(enemy, combat.EnemyState):
                return True

            angle = kwargs.get("angle")
            if isinstance(angle, int):
                history = movement_angles.get(enemy.enemy_id)
                if history is not None:
                    history.append(angle % 360)
            return True

        with patch.object(combat, "enemy_speed_for_type", return_value=0.0), patch.object(
            combat,
            "_can_enemy_fire",
            return_value=False,
        ), patch.object(
            combat,
            "_enemy_should_strafe",
            return_value=True,
        ), patch.object(
            combat,
            "_rotate_towards_angle",
            side_effect=lambda current, target, step: current,
        ), patch.object(combat, "_move_enemy_with_collision", side_effect=record_enemy_movement):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return {
            enemy_id: tuple(angles)
            for enemy_id, angles in movement_angles.items()
        }

    def _run_scripted_mine_arm_transition_boundary_scenario(
        self,
    ) -> tuple[int, dict[int, tuple[tuple[int, ...], int, int]], int, int]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.0,
            input_script="20:+SHOOT;35:-SHOOT;80:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=0,
                x=40.0,
                y=50.0,
                health=18.0,
                max_health=18.0,
                angle=180,
                target_angle=180,
                load_count=0,
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
        gameplay_scene._player_explosive_detonations = 0  # type: ignore[attr-defined]

        deployment_frames: list[int] = []
        frame_samples: dict[int, tuple[tuple[int, ...], int, int]] = {}

        original_deploy = gameplay_scene_module.deploy_player_explosive_from_shot
        original_update_player_explosives = gameplay_scene_module.update_player_explosives

        def record_mine_deploy(*args: object, **kwargs: object) -> combat.PlayerExplosive | None:
            explosive = original_deploy(*args, **kwargs)
            if explosive is not None and explosive.kind == "mine":
                deployment_frames.append(app.context.runtime.simulation_frame)
            return explosive

        def record_explosive_update(*args: object, **kwargs: object) -> combat.PlayerExplosiveReport:
            frame = app.context.runtime.simulation_frame
            explosives = args[0] if args else []
            mine_arming_before: tuple[int, ...] = ()
            if isinstance(explosives, list):
                mine_arming_before = tuple(
                    explosive.arming_ticks
                    for explosive in explosives
                    if isinstance(explosive, combat.PlayerExplosive) and explosive.kind == "mine"
                )

            report = original_update_player_explosives(*args, **kwargs)

            mine_count_after = 0
            if isinstance(explosives, list):
                mine_count_after = sum(
                    1
                    for explosive in explosives
                    if isinstance(explosive, combat.PlayerExplosive) and explosive.kind == "mine"
                )
            frame_samples[frame] = (
                mine_arming_before,
                report.detonations,
                mine_count_after,
            )
            return report

        with patch.object(combat, "PLAYER_MINE_SLEEP_TICKS", 2), patch.object(
            gameplay_scene_module,
            "update_enemy_behavior",
            return_value=combat.EnemyBehaviorReport(),
        ), patch.object(
            gameplay_scene_module,
            "update_enemy_projectiles",
            return_value=combat.EnemyProjectileReport(),
        ), patch.object(
            gameplay_scene_module,
            "deploy_player_explosive_from_shot",
            side_effect=record_mine_deploy,
        ), patch.object(
            gameplay_scene_module,
            "update_player_explosives",
            side_effect=record_explosive_update,
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertTrue(deployment_frames)
        return (
            deployment_frames[0],
            frame_samples,
            app.context.runtime.player_shots_fired_total,
            app.context.runtime.player_explosive_detonations_total,
        )

    def _run_scripted_c4_remote_trigger_boundary_scenario(
        self,
    ) -> tuple[
        dict[int, tuple[tuple[int, ...], int, int]],
        int | None,
        int,
        int,
        int,
        int,
        int,
        int,
    ]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.6,
            input_script="20:+SHOOT;35:-SHOOT;60:+SHOOT;75:-SHOOT;120:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 10):
            for tile_x in range(1, 6):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False
        player.grant_weapon(9)
        for bullet_type in range(len(player.bullets)):
            player.bullets[bullet_type] = 0
        self.assertGreater(grant_bullet_ammo(player, 6, 2), 0)
        player.current_weapon = 9
        player.load_count = player.current_weapon_profile.loading_time

        gameplay_scene._player_explosive_detonations = 0  # type: ignore[attr-defined]

        frame_samples: dict[int, tuple[tuple[int, ...], int, int]] = {}
        remote_trigger_frame: int | None = None
        original_update_player_explosives = gameplay_scene_module.update_player_explosives

        def record_explosive_update(*args: object, **kwargs: object) -> combat.PlayerExplosiveReport:
            nonlocal remote_trigger_frame

            frame = app.context.runtime.simulation_frame
            explosives = args[0] if args else []
            c4_fuse_before: tuple[int, ...] = ()
            if isinstance(explosives, list):
                c4_fuse_before = tuple(
                    explosive.fuse_ticks
                    for explosive in explosives
                    if isinstance(explosive, combat.PlayerExplosive) and explosive.kind == "c4"
                )
                if remote_trigger_frame is None and any(fuse <= 0 for fuse in c4_fuse_before):
                    remote_trigger_frame = frame

            report = original_update_player_explosives(*args, **kwargs)

            c4_count_after = 0
            if isinstance(explosives, list):
                c4_count_after = sum(
                    1
                    for explosive in explosives
                    if isinstance(explosive, combat.PlayerExplosive) and explosive.kind == "c4"
                )
            frame_samples[frame] = (
                c4_fuse_before,
                report.detonations,
                c4_count_after,
            )
            return report

        with patch.object(combat, "PLAYER_C4_FUSE_TICKS", 40), patch.object(
            gameplay_scene_module,
            "update_enemy_behavior",
            return_value=combat.EnemyBehaviorReport(),
        ), patch.object(
            gameplay_scene_module,
            "update_enemy_projectiles",
            return_value=combat.EnemyProjectileReport(),
        ), patch.object(
            gameplay_scene_module,
            "update_player_explosives",
            side_effect=record_explosive_update,
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            frame_samples,
            remote_trigger_frame,
            app.context.runtime.player_shots_fired_total,
            app.context.runtime.player_explosive_detonations_total,
            app.context.runtime.player_weapon_slot,
            app.context.runtime.player_current_ammo_type_index,
            app.context.runtime.player_current_ammo_units,
            app.context.runtime.player_ammo_pools[6],
        )

    def _run_scripted_empty_weapon_fallback_scenario(self) -> tuple[int, int, int, int, int, int]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.9,
            input_script="20:+SHOOT;35:-SHOOT;60:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        enemy_projectiles = getattr(gameplay_scene, "_enemy_projectiles", None)
        player_explosives = getattr(gameplay_scene, "_player_explosives", None)
        if (
            player is None
            or enemies is None
            or crates is None
            or enemy_projectiles is None
            or player_explosives is None
        ):
            self.skipTest("gameplay scene did not initialize combat state")

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        player.x = 40.0
        player.y = 40.0
        player.angle = 0
        player.health = player.max_health
        player.dead = False
        player.grant_weapon(1)
        for bullet_type in range(len(player.bullets)):
            player.bullets[bullet_type] = 0
        player.current_weapon = 1
        player.load_count = player.current_weapon_profile.loading_time
        player.shots_fired_total = 0

        with patch.object(
            gameplay_scene_module,
            "update_enemy_behavior",
            return_value=combat.EnemyBehaviorReport(),
        ), patch.object(
            gameplay_scene_module,
            "update_enemy_projectiles",
            return_value=combat.EnemyProjectileReport(),
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.player_weapon_slot,
            app.context.runtime.player_shots_fired_total,
            app.context.runtime.player_current_ammo_type_index,
            app.context.runtime.player_current_ammo_units,
            app.context.runtime.player_current_ammo_capacity,
            app.context.runtime.player_ammo_pools[0],
        )

    def _run_scripted_mine_simultaneous_edge_contacts_scenario(self) -> tuple[int, int, int, int]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.0,
            input_script="20:+SHOOT;35:-SHOOT;80:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 10):
            for tile_x in range(1, 8):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        for enemy_id, enemy_x in enumerate((32.0, 48.0)):
            enemies.append(
                combat.EnemyState(
                    enemy_id=enemy_id,
                    type_index=5,
                    x=enemy_x,
                    y=50.0,
                    health=10.0,
                    max_health=10.0,
                    angle=180,
                    target_angle=180,
                    load_count=0,
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

        with patch.object(combat, "PLAYER_MINE_SLEEP_TICKS", 2), patch.object(
            gameplay_scene_module,
            "update_enemy_behavior",
            return_value=combat.EnemyBehaviorReport(),
        ), patch.object(
            gameplay_scene_module,
            "update_enemy_projectiles",
            return_value=combat.EnemyProjectileReport(),
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            app.context.runtime.player_shots_fired_total,
            app.context.runtime.player_explosive_detonations_total,
            app.context.runtime.enemies_killed_by_player,
            app.context.runtime.enemies_alive,
        )

    def _run_scripted_mine_chained_detonations_scenario(self) -> tuple[int, int, int, float, bool]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.8,
            input_script="20:+SHOOT;35:-SHOOT;60:+SHOOT;75:-SHOOT;120:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 12):
            for tile_x in range(1, 8):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=6,
                x=40.0,
                y=50.0,
                health=120.0,
                max_health=120.0,
                angle=180,
                target_angle=180,
                load_count=0,
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
        self.assertGreater(grant_bullet_ammo(player, 8, 2), 0)
        player.current_weapon = 11
        player.load_count = player.current_weapon_profile.loading_time

        with patch.object(combat, "PLAYER_MINE_SLEEP_TICKS", 2), patch.object(
            gameplay_scene_module,
            "update_enemy_behavior",
            return_value=combat.EnemyBehaviorReport(),
        ), patch.object(
            gameplay_scene_module,
            "update_enemy_projectiles",
            return_value=combat.EnemyProjectileReport(),
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        enemy = enemies[0]
        return (
            app.context.runtime.player_shots_fired_total,
            app.context.runtime.player_explosive_detonations_total,
            app.context.runtime.enemies_killed_by_player,
            enemy.health,
            enemy.alive,
        )

    def _run_scripted_mine_nearest_contact_ordering_scenario(
        self,
    ) -> tuple[tuple[tuple[float, float], ...], int]:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.0,
            input_script="20:+SHOOT;35:-SHOOT;80:QUIT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
        level, player, enemies, crates, enemy_projectiles, player_explosives = self._extract_combat_state_or_skip(
            gameplay_scene,
        )

        blocks = list(level.blocks)

        for tile_y in range(1, 10):
            for tile_x in range(1, 8):
                self._set_block(blocks, level, tile_x=tile_x, tile_y=tile_y, block_type=FLOOR_BLOCK_TYPE)

        gameplay_scene._level = replace(level, blocks=tuple(blocks))  # type: ignore[attr-defined]

        enemies.clear()
        crates.clear()
        enemy_projectiles.clear()
        player_explosives.clear()

        enemies.append(
            combat.EnemyState(
                enemy_id=0,
                type_index=0,
                x=40.0,
                y=64.0,
                health=18.0,
                max_health=18.0,
                angle=180,
                target_angle=180,
                load_count=0,
            ),
        )
        enemies.append(
            combat.EnemyState(
                enemy_id=1,
                type_index=0,
                x=40.0,
                y=50.0,
                health=18.0,
                max_health=18.0,
                angle=180,
                target_angle=180,
                load_count=0,
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

        los_endpoints: list[tuple[float, float]] = []
        original_line_of_sight_clear = combat._line_of_sight_clear

        def record_line_of_sight(*args: object, **kwargs: object) -> bool:
            end_x = kwargs.get("end_x")
            end_y = kwargs.get("end_y")
            if isinstance(end_x, float) and isinstance(end_y, float):
                los_endpoints.append((end_x, end_y))
            return original_line_of_sight_clear(*args, **kwargs)

        with patch.object(combat, "PLAYER_MINE_SLEEP_TICKS", 2), patch.object(
            gameplay_scene_module,
            "update_enemy_behavior",
            return_value=combat.EnemyBehaviorReport(),
        ), patch.object(
            gameplay_scene_module,
            "update_enemy_projectiles",
            return_value=combat.EnemyProjectileReport(),
        ), patch.object(
            combat,
            "_line_of_sight_clear",
            side_effect=record_line_of_sight,
        ):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        return (
            tuple(los_endpoints),
            app.context.runtime.player_explosive_detonations_total,
        )

    def test_scripted_turn_changes_player_angle(self) -> None:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.6,
            input_script="5:+TURN_LEFT;11:-TURN_LEFT",
        )
        app = self._create_app_or_skip(config)

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertNotEqual(app.context.runtime.player_angle_degrees, 0)

    def test_scripted_shoot_increments_shot_counter(self) -> None:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.8,
            input_script="5:+SHOOT;40:-SHOOT",
        )
        app = self._create_app_or_skip(config)

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertGreater(app.context.runtime.player_shots_fired_total, 0)
        self.assertGreaterEqual(app.context.runtime.enemies_total, app.context.runtime.enemies_alive)

    def test_scripted_shop_open_and_buy_attempt_sets_shop_runtime(self) -> None:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=1.0,
            input_script="15:+SHOP;16:+SHOOT;17:+SHOOT;18:+SHOOT;19:+SHOOT;20:+SHOOT",
        )
        app = self._create_app_or_skip(config)

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertTrue(app.context.runtime.shop_active)
        self.assertEqual(app.context.runtime.shop_last_action, "buy")
        self.assertEqual(app.context.runtime.shop_last_category, "weapon")
        self.assertFalse(app.context.runtime.shop_last_success)
        self.assertEqual(app.context.runtime.shop_last_reason, "NO CASH")

    def test_scripted_shield_buy_plus_energy_crate_reaches_shield_cap(self) -> None:
        (
            player_health,
            player_shield,
            crates_collected,
            last_action,
            last_category,
            last_success,
        ) = self._run_scripted_shield_energy_scenario(sell_after_collect=False)

        self.assertEqual(player_shield, 1)
        self.assertEqual(player_health, 110)
        self.assertEqual(crates_collected, 1)
        self.assertEqual(last_action, "buy")
        self.assertEqual(last_category, "shield")
        self.assertTrue(last_success)

    def test_scripted_shield_sell_after_energy_clamps_health_to_base_cap(self) -> None:
        (
            player_health,
            player_shield,
            crates_collected,
            last_action,
            last_category,
            last_success,
        ) = self._run_scripted_shield_energy_scenario(sell_after_collect=True)

        self.assertEqual(player_shield, 0)
        self.assertEqual(player_health, 100)
        self.assertEqual(crates_collected, 1)
        self.assertEqual(last_action, "sell")
        self.assertEqual(last_category, "shield")
        self.assertTrue(last_success)

    def test_scripted_mixed_crate_collect_and_destroy_updates_runtime_consistently(self) -> None:
        crates_collected, crates_destroyed, crates_alive, player_health, weapon_one_owned = (
            self._run_scripted_crate_collect_destroy_mix_scenario()
        )

        self.assertEqual(crates_collected, 1)
        self.assertEqual(crates_destroyed, 1)
        self.assertEqual(crates_alive, 0)
        self.assertEqual(player_health, 100)
        self.assertFalse(weapon_one_owned)

    def test_scripted_mine_and_c4_update_explosive_runtime(self) -> None:
        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=2.5,
            input_script="20:+SHOOT;35:-SHOOT;40:WEAPON=9;55:+SHOOT;70:-SHOOT",
        )
        app = self._create_app_or_skip(config)

        gameplay_scene = self._enter_gameplay_or_skip(app)
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
        self.assertEqual(
            app.context.runtime.player_explosives_active,
            app.context.runtime.player_mines_active + app.context.runtime.player_c4_active,
        )

    def test_scripted_mine_arm_transition_uses_n_minus_1_n_n_plus_1_timing(self) -> None:
        deploy_frame, frame_samples, shots, detonations = self._run_scripted_mine_arm_transition_boundary_scenario()

        arm_transition_frame = deploy_frame + 2
        self.assertIn(arm_transition_frame - 1, frame_samples)
        self.assertIn(arm_transition_frame, frame_samples)
        self.assertIn(arm_transition_frame + 1, frame_samples)

        n_minus_1_arming, n_minus_1_detonations, n_minus_1_mines_after = frame_samples[
            arm_transition_frame - 1
        ]
        n_arming, n_detonations, n_mines_after = frame_samples[arm_transition_frame]
        n_plus_1_arming, n_plus_1_detonations, n_plus_1_mines_after = frame_samples[arm_transition_frame + 1]

        self.assertEqual(shots, 1)
        self.assertEqual(detonations, 1)
        self.assertEqual(n_minus_1_arming, (2,))
        self.assertEqual(n_minus_1_detonations, 0)
        self.assertEqual(n_minus_1_mines_after, 1)

        self.assertEqual(n_arming, (1,))
        self.assertEqual(n_detonations, 1)
        self.assertEqual(n_mines_after, 0)

        self.assertEqual(n_plus_1_arming, ())
        self.assertEqual(n_plus_1_detonations, 0)
        self.assertEqual(n_plus_1_mines_after, 0)

    def test_scripted_c4_remote_trigger_uses_n_minus_1_n_n_plus_1_timing(self) -> None:
        (
            frame_samples,
            remote_frame,
            shots,
            detonations,
            weapon_slot,
            current_ammo_type,
            current_ammo_units,
            c4_ammo_pool,
        ) = self._run_scripted_c4_remote_trigger_boundary_scenario()

        self.assertIsNotNone(remote_frame)
        assert remote_frame is not None

        self.assertIn(remote_frame - 1, frame_samples)
        self.assertIn(remote_frame, frame_samples)
        self.assertIn(remote_frame + 1, frame_samples)

        n_minus_1_fuse, n_minus_1_detonations, n_minus_1_c4_after = frame_samples[remote_frame - 1]
        n_fuse, n_detonations, n_c4_after = frame_samples[remote_frame]
        n_plus_1_fuse, n_plus_1_detonations, n_plus_1_c4_after = frame_samples[remote_frame + 1]

        self.assertEqual(shots, 2)
        self.assertEqual(detonations, 1)
        self.assertEqual(weapon_slot, 9)
        self.assertEqual(current_ammo_type, 6)
        self.assertEqual(current_ammo_units, 1)
        self.assertEqual(c4_ammo_pool, 1)
        self.assertEqual(current_ammo_units, c4_ammo_pool)
        self.assertEqual(bullet_capacity_units_for_type(6), 100)
        self.assertTrue(n_minus_1_fuse)
        self.assertTrue(all(fuse > 0 for fuse in n_minus_1_fuse))
        self.assertEqual(n_minus_1_detonations, 0)
        self.assertEqual(n_minus_1_c4_after, 1)

        self.assertTrue(any(fuse <= 0 for fuse in n_fuse))
        self.assertEqual(n_detonations, 1)
        self.assertEqual(n_c4_after, 0)

        self.assertEqual(n_plus_1_fuse, ())
        self.assertEqual(n_plus_1_detonations, 0)
        self.assertEqual(n_plus_1_c4_after, 0)

    def test_scripted_empty_weapon_fallback_keeps_runtime_ammo_and_shot_telemetry_stable(self) -> None:
        weapon_slot, shots, ammo_type, ammo_units, ammo_capacity, pistol_pool = (
            self._run_scripted_empty_weapon_fallback_scenario()
        )

        self.assertEqual(weapon_slot, 0)
        self.assertEqual(shots, 0)
        self.assertEqual(ammo_type, -1)
        self.assertEqual(ammo_units, 0)
        self.assertEqual(ammo_capacity, 0)
        self.assertEqual(pistol_pool, 0)

    def test_scripted_mine_simultaneous_enemy_edge_contacts_hit_both_targets(self) -> None:
        shots, detonations, kills, enemies_alive = self._run_scripted_mine_simultaneous_edge_contacts_scenario()

        self.assertEqual(shots, 1)
        self.assertEqual(detonations, 1)
        self.assertEqual(kills, 2)
        self.assertEqual(enemies_alive, 0)

    def test_scripted_mine_chained_contact_detonations_across_two_shots(self) -> None:
        shots, detonations, kills, enemy_health, enemy_alive = self._run_scripted_mine_chained_detonations_scenario()

        self.assertEqual(shots, 2)
        self.assertEqual(detonations, 2)
        self.assertEqual(kills, 0)
        self.assertTrue(enemy_alive)
        self.assertGreater(enemy_health, 0.0)
        self.assertLess(enemy_health, 120.0)

    def test_scripted_mine_multi_contact_prioritizes_nearest_contact_ordering(self) -> None:
        los_endpoints, detonations = self._run_scripted_mine_nearest_contact_ordering_scenario()

        self.assertGreaterEqual(detonations, 1)
        self.assertTrue(los_endpoints)

        first_end_x, first_end_y = los_endpoints[0]
        self.assertAlmostEqual(first_end_x, 54.0)
        self.assertAlmostEqual(first_end_y, 59.0)

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

    def test_scripted_enemy_strafe_blocked_lane_retries_opposite_direction(self) -> None:
        movement_calls, shots = self._run_scripted_enemy_strafe_fallback_scenario()

        self.assertEqual(shots, 0)
        self.assertGreaterEqual(len(movement_calls), 3)

        blocked_lane_retry_seen = False
        for index in range(len(movement_calls) - 1):
            primary_angle, primary_moved = movement_calls[index]
            fallback_angle, fallback_moved = movement_calls[index + 1]
            if (
                primary_angle == 45
                and not primary_moved
                and fallback_angle == 225
                and fallback_moved
            ):
                blocked_lane_retry_seen = True
                break

        self.assertTrue(blocked_lane_retry_seen)

    def test_scripted_projectile_expiry_crate_cover_reduces_splash_damage(self) -> None:
        open_damage, open_hits, open_projectiles, open_collected, _ = (
            self._run_scripted_projectile_expiry_crate_cover_scenario(with_cover=False)
        )
        cover_damage, cover_hits, cover_projectiles, cover_collected, cover_crate_health = (
            self._run_scripted_projectile_expiry_crate_cover_scenario(with_cover=True)
        )

        self.assertEqual(open_hits, 1)
        self.assertEqual(cover_hits, 1)
        self.assertGreater(open_damage, 0.0)
        self.assertGreater(cover_damage, 0.0)
        self.assertLess(cover_damage, open_damage)
        self.assertEqual(open_projectiles, 0)
        self.assertEqual(cover_projectiles, 0)
        self.assertEqual(open_collected, 0)
        self.assertEqual(cover_collected, 0)
        self.assertGreater(cover_crate_health, 0.0)
        self.assertLess(cover_crate_health, 12.0)

    def test_scripted_dead_player_projectile_telemetry_gates_hits_and_damage(self) -> None:
        (
            enemy_hits,
            enemy_damage,
            active_projectiles,
            player_hits_taken,
            player_damage_taken,
            game_over_active,
            crate_health,
        ) = self._run_scripted_dead_player_projectile_telemetry_gating_scenario()

        self.assertEqual(enemy_hits, 0)
        self.assertEqual(enemy_damage, 0.0)
        self.assertEqual(active_projectiles, 0)
        self.assertEqual(player_hits_taken, 0)
        self.assertEqual(player_damage_taken, 0.0)
        self.assertTrue(game_over_active)
        self.assertEqual(crate_health, 12.0)

    def test_scripted_unknown_owner_projectile_is_preserved_by_owner_gating(self) -> None:
        enemy_hits, player_hits_taken, active_projectiles, player_damage_taken = (
            self._run_scripted_unknown_owner_projectile_retention_scenario()
        )

        self.assertEqual(enemy_hits, 1)
        self.assertEqual(player_hits_taken, 1)
        self.assertGreater(player_damage_taken, 0.0)
        self.assertEqual(active_projectiles, 0)

    def test_scripted_dead_player_clears_projectile_and_explosive_buffers_same_tick(self) -> None:
        (
            active_projectiles,
            active_explosives,
            detonations,
            enemy_hits,
            enemy_damage,
            game_over_active,
        ) = self._run_scripted_dead_player_buffer_cleanup_scenario()

        self.assertEqual(active_projectiles, 0)
        self.assertEqual(active_explosives, 0)
        self.assertEqual(detonations, 0)
        self.assertEqual(enemy_hits, 0)
        self.assertEqual(enemy_damage, 0.0)
        self.assertTrue(game_over_active)

    def test_scripted_player_death_halts_followup_projectile_crate_side_effects(self) -> None:
        enemy_hits, enemy_damage, crate_health, active_projectiles, player_hits_taken, game_over_active = (
            self._run_scripted_player_death_halts_followup_projectile_side_effects_scenario()
        )

        self.assertEqual(enemy_hits, 1)
        self.assertEqual(enemy_damage, 5.0)
        self.assertEqual(crate_health, 12.0)
        self.assertEqual(active_projectiles, 0)
        self.assertEqual(player_hits_taken, 1)
        self.assertTrue(game_over_active)

    def test_scripted_prelethal_projectile_side_effects_remain_before_death_short_circuit(self) -> None:
        enemy_hits, enemy_damage, crate_health, active_projectiles, player_hits_taken, game_over_active = (
            self._run_scripted_player_death_halts_followup_projectile_side_effects_scenario(lethal_first=False)
        )

        self.assertEqual(enemy_hits, 1)
        self.assertEqual(enemy_damage, 5.0)
        self.assertEqual(crate_health, 7.0)
        self.assertEqual(active_projectiles, 0)
        self.assertEqual(player_hits_taken, 1)
        self.assertTrue(game_over_active)

    def test_scripted_multi_enemy_strafe_switches_are_staggered_during_reload(self) -> None:
        movement_angles = self._run_scripted_multi_enemy_strafe_stagger_scenario()

        first_enemy_angles = movement_angles[0]
        second_enemy_angles = movement_angles[1]
        self.assertGreaterEqual(len(first_enemy_angles), 6)
        self.assertGreaterEqual(len(second_enemy_angles), 6)

        def first_switch_tick(angles: tuple[int, ...]) -> int | None:
            for index in range(1, len(angles)):
                if angles[index] != angles[index - 1]:
                    return index
            return None

        first_enemy_switch = first_switch_tick(first_enemy_angles)
        second_enemy_switch = first_switch_tick(second_enemy_angles)

        self.assertIsNotNone(first_enemy_switch)
        self.assertIsNotNone(second_enemy_switch)
        assert first_enemy_switch is not None
        assert second_enemy_switch is not None
        self.assertEqual(first_enemy_switch, 4)
        self.assertEqual(second_enemy_switch - first_enemy_switch, 1)
        self.assertNotEqual(first_enemy_switch, second_enemy_switch)
        self.assertGreater(second_enemy_switch, first_enemy_switch)

    def test_scripted_enemy_explosive_long_range_shot_applies_forward_pressure(self) -> None:
        start_x, start_y, end_x, pressured_y, pressured_shots = self._run_scripted_enemy_explosive_pressure_scenario(
            pressure_trigger_ratio=0.5,
        )
        _, _, _, baseline_y, baseline_shots = self._run_scripted_enemy_explosive_pressure_scenario(
            pressure_trigger_ratio=0.99,
        )

        self.assertGreaterEqual(pressured_shots, 1)
        self.assertGreaterEqual(baseline_shots, 1)
        self.assertLess(pressured_y, start_y)
        self.assertLess(pressured_y, baseline_y)
        self.assertGreaterEqual(baseline_y - pressured_y, 2.0)
        self.assertGreater(abs(end_x - start_x), 0.0)

    def test_scripted_enemy_lost_sight_after_contact_starts_chase_window(self) -> None:
        seen_start_y, seen_end_y, seen_chase_ticks, seen_flag = self._run_scripted_enemy_lost_sight_chase_scenario(
            prior_seen=True,
        )
        unseen_start_y, unseen_end_y, unseen_chase_ticks, unseen_flag = self._run_scripted_enemy_lost_sight_chase_scenario(
            prior_seen=False,
        )

        self.assertFalse(seen_flag)
        self.assertFalse(unseen_flag)
        self.assertGreater(seen_chase_ticks, 0)
        self.assertEqual(unseen_chase_ticks, 0)
        self.assertLess(seen_end_y, seen_start_y)

    def test_scripted_enemy_patrol_uses_idle_then_burst_behavior(self) -> None:
        idle_start_x, idle_start_y, idle_end_x, idle_end_y, idle_walk_ticks = self._run_scripted_enemy_patrol_burst_scenario(
            patrol_roll_value=0,
        )
        burst_start_x, burst_start_y, burst_end_x, burst_end_y, burst_walk_ticks = self._run_scripted_enemy_patrol_burst_scenario(
            patrol_roll_value=1,
        )

        self.assertEqual(idle_walk_ticks, 0)
        self.assertEqual(idle_end_x, idle_start_x)
        self.assertEqual(idle_end_y, idle_start_y)
        self.assertGreaterEqual(burst_walk_ticks, 0)
        self.assertGreater(abs(burst_end_x - burst_start_x) + abs(burst_end_y - burst_start_y), 5.0)

    def test_scripted_enemy_patrol_turn_roll_waits_until_aligned(self) -> None:
        angle, target_angle, walk_ticks = self._run_scripted_enemy_patrol_turn_lock_scenario()

        self.assertEqual(target_angle, 90)
        self.assertGreater(angle, 0)
        self.assertLessEqual(angle, 90)
        self.assertGreater(walk_ticks, 0)

    def test_scripted_enemy_los_uses_legacy_trace_step(self) -> None:
        steps = self._run_scripted_enemy_los_trace_step_scenario()

        self.assertTrue(steps)
        self.assertTrue(all(step == combat.ENEMY_LINE_OF_SIGHT_TRACE_STEP for step in steps))
        self.assertEqual(combat.ENEMY_LINE_OF_SIGHT_TRACE_STEP, 5)

    def test_scripted_enemy_front_vision_arc_blocks_rear_detection(self) -> None:
        shots, hits, damage = self._run_scripted_enemy_los_corner_graze_scenario(
            wall_tiles=set(),
            enemy_type_index=0,
            enemy_x=40.0,
            enemy_y=80.0,
            enemy_angle=0,
            enemy_walk_ticks=120,
            enemy_load_count=10,
            player_x=40.0,
            player_y=40.0,
        )

        self.assertEqual(shots, 0)
        self.assertEqual(hits, 0)
        self.assertEqual(damage, 0.0)

    def test_scripted_enemy_vision_distance_blocks_far_detection(self) -> None:
        shots, hits, damage = self._run_scripted_enemy_los_corner_graze_scenario(
            wall_tiles=set(),
            enemy_type_index=0,
            enemy_x=40.0,
            enemy_y=260.0,
            enemy_angle=180,
            enemy_walk_ticks=120,
            enemy_load_count=10,
            player_x=40.0,
            player_y=40.0,
        )

        self.assertEqual(shots, 0)
        self.assertEqual(hits, 0)
        self.assertEqual(damage, 0.0)

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

    def test_scripted_enemy_direct_shot_corner_graze_blocks_fire_with_legacy_los_step(self) -> None:
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

        self.assertEqual(blocked_shots, 0)
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

    def test_scripted_main_menu_manual_start_enters_gameplay_without_autostart(self) -> None:
        config = RuntimeConfig(
            autostart_gameplay=False,
            max_seconds=1.0,
            input_script="0:+SHOOT;20:QUIT",
        )
        app = self._create_app_or_skip(config)
        app.scene_manager.update(0.025)
        self.assertEqual(app.scene_manager.current_scene_name, "main_menu")

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertEqual(app.scene_manager.current_scene_name, "gameplay")
        self.assertGreater(app.context.runtime.player_health, 0)

    def test_scripted_level_completion_advances_session_index_for_manual_progression_flow(self) -> None:
        config = RuntimeConfig(
            autostart_gameplay=False,
            max_seconds=1.2,
            input_script="0:+SHOOT;8:+SHOOT;40:QUIT",
        )
        app = self._create_app_or_skip(config)
        app.scene_manager.update(0.025)
        self.assertEqual(app.scene_manager.current_scene_name, "main_menu")

        original_spawn_enemies = gameplay_scene_module.spawn_enemies_for_level
        spawn_calls = 0

        def spawn_enemies_once_empty(level: object, *, player_x: float, player_y: float) -> object:
            nonlocal spawn_calls
            spawn_calls += 1
            if spawn_calls == 1:
                return ()
            return original_spawn_enemies(level, player_x=player_x, player_y=player_y)

        with patch.object(gameplay_scene_module, "spawn_enemies_for_level", side_effect=spawn_enemies_once_empty):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertGreaterEqual(spawn_calls, 2)
        self.assertEqual(app.context.session.level_index, 1)
        self.assertEqual(app.scene_manager.current_scene_name, "gameplay")

    def test_scripted_run_complete_fallback_returns_to_main_menu_with_reset_index(self) -> None:
        config = RuntimeConfig(
            autostart_gameplay=False,
            max_seconds=1.2,
            input_script="0:+SHOOT;8:+SHOOT;40:QUIT",
        )
        app = self._create_app_or_skip(config)
        app.context.session.level_index = 9
        app.scene_manager.update(0.025)
        self.assertEqual(app.scene_manager.current_scene_name, "main_menu")

        original_spawn_enemies = gameplay_scene_module.spawn_enemies_for_level

        def spawn_enemies_once_empty(level: object, *, player_x: float, player_y: float) -> object:
            if app.context.session.level_index == 9:
                return ()
            return original_spawn_enemies(level, player_x=player_x, player_y=player_y)

        with patch.object(gameplay_scene_module, "spawn_enemies_for_level", side_effect=spawn_enemies_once_empty):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertEqual(app.scene_manager.current_scene_name, "main_menu")
        self.assertEqual(app.context.session.level_index, 0)
        self.assertEqual(app.context.runtime.progression_event, "run_complete")
        self.assertFalse(app.context.runtime.progression_has_next_level)

        behavior_digest = (
            app.scene_manager.current_scene_name,
            app.context.session.level_index,
            app.context.runtime.progression_event,
            app.context.runtime.progression_from_level_index,
            app.context.runtime.progression_to_level_index,
            app.context.runtime.progression_has_next_level,
            app.context.runtime.progression_ticks_remaining,
            app.context.runtime.player_health,
            app.context.runtime.player_cash,
            app.context.runtime.player_shots_fired_total,
            app.context.runtime.enemies_total,
            app.context.runtime.enemies_alive,
            app.context.runtime.crates_total,
            app.context.runtime.crates_alive,
            app.context.runtime.shop_active,
            app.context.runtime.game_over_active,
        )
        self.assertEqual(
            behavior_digest,
            (
                "main_menu",
                0,
                "run_complete",
                9,
                0,
                False,
                0,
                100,
                0,
                0,
                0,
                0,
                11,
                11,
                False,
                False,
            ),
        )

    def test_scripted_manual_progression_loop_reaches_run_complete_and_returns_to_menu(self) -> None:
        config = RuntimeConfig(
            autostart_gameplay=False,
            max_seconds=2.2,
            input_script="0:+SHOOT",
        )
        app = self._create_app_or_skip(config)
        app.context.session.level_index = 8
        app.scene_manager.update(0.025)
        self.assertEqual(app.scene_manager.current_scene_name, "main_menu")

        original_spawn_enemies = gameplay_scene_module.spawn_enemies_for_level

        def spawn_enemies_for_progression_loop(level: object, *, player_x: float, player_y: float) -> object:
            if app.context.session.level_index in (8, 9):
                return ()
            return original_spawn_enemies(level, player_x=player_x, player_y=player_y)

        with patch.object(gameplay_scene_module, "spawn_enemies_for_level", side_effect=spawn_enemies_for_progression_loop):
            exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertEqual(app.scene_manager.current_scene_name, "main_menu")
        self.assertEqual(app.context.session.level_index, 0)
        self.assertEqual(app.context.runtime.progression_event, "run_complete")
        self.assertFalse(app.context.runtime.progression_has_next_level)

    def test_scripted_main_menu_quit_selection_stops_run_without_core_quit_event(self) -> None:
        config = RuntimeConfig(
            autostart_gameplay=False,
            max_seconds=1.0,
            input_script="0:+MOVE_BACKWARD;1:+SHOOT",
        )
        app = self._create_app_or_skip(config)
        app.scene_manager.update(0.025)
        self.assertEqual(app.scene_manager.current_scene_name, "main_menu")

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertEqual(app.scene_manager.current_scene_name, "main_menu")
        self.assertFalse(app.context.runtime.running)


if __name__ == "__main__":
    unittest.main()

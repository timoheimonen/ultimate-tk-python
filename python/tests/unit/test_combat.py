from __future__ import annotations

import math
import sys
from pathlib import Path
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.formats.lev import (
    DIFF_BULLETS,
    DIFF_ENEMIES,
    DIFF_WEAPONS,
    Block,
    CrateCounts,
    CrateInfo,
    GeneralLevelInfo,
    LevelData,
)
import ultimatetk.systems.combat as combat_module
from ultimatetk.systems.combat import (
    CrateState,
    EnemyProjectile,
    EnemyState,
    alive_crate_count,
    advance_crate_effects,
    advance_enemy_effects,
    alive_enemy_count,
    collect_crates_for_player,
    deploy_player_explosive_from_shot,
    is_player_explosive_weapon_slot,
    resolve_enemy_attack_against_player,
    resolve_shot_against_enemies,
    spawn_crates_for_level,
    spawn_enemies_for_level,
    update_player_explosives,
    update_enemy_behavior,
    update_enemy_projectiles,
)
from ultimatetk.systems.player_control import PlayerState, ShotEvent


def _build_level(
    *,
    width: int = 10,
    height: int = 10,
    walls: set[tuple[int, int]] | None = None,
    start: tuple[int, int] = (2, 2),
    enemies: tuple[int, ...] | None = None,
    normal_crate_counts: CrateCounts | None = None,
    normal_crate_info: tuple[CrateInfo, ...] = (),
) -> LevelData:
    wall_tiles = walls or set()
    blocks = []
    for y in range(height):
        for x in range(width):
            block_type = 1 if (x, y) in wall_tiles else 0
            blocks.append(Block(type=block_type, num=0, shadow=0))

    crate_counts = (
        normal_crate_counts
        if normal_crate_counts is not None
        else CrateCounts(
            weapon_crates=tuple(0 for _ in range(DIFF_WEAPONS)),
            bullet_crates=tuple(0 for _ in range(DIFF_BULLETS)),
            energy_crates=0,
        )
    )
    enemy_counts = enemies or tuple(0 for _ in range(DIFF_ENEMIES))
    return LevelData(
        version=5,
        level_x_size=width,
        level_y_size=height,
        blocks=tuple(blocks),
        player_start_x=(start[0], start[0]),
        player_start_y=(start[1], start[1]),
        spots=(),
        steams=(),
        general_info=GeneralLevelInfo(comment="", time_limit=0, enemies=enemy_counts),
        normal_crate_counts=crate_counts,
        deathmatch_crate_counts=crate_counts,
        normal_crate_info=normal_crate_info,
        deathmatch_crate_info=(),
    )


class CombatSystemTests(unittest.TestCase):
    def test_spawn_uses_level_enemy_counts(self) -> None:
        level = _build_level(enemies=(1, 0, 0, 0, 0, 0, 0, 0))

        spawned = spawn_enemies_for_level(level, player_x=40.0, player_y=40.0)

        self.assertEqual(len(spawned), 1)
        self.assertEqual(spawned[0].type_index, 0)
        self.assertEqual((int(spawned[0].x), int(spawned[0].y)), (40, 80))

    def test_spawn_crates_uses_level_crate_info_positions(self) -> None:
        crate_info = (
            CrateInfo(type1=2, type2=0, x=70, y=90),
            CrateInfo(type1=0, type2=3, x=110, y=90),
        )
        level = _build_level(normal_crate_info=crate_info)

        spawned = spawn_crates_for_level(level, player_x=40.0, player_y=40.0)

        self.assertEqual(len(spawned), 2)
        self.assertEqual(spawned[0].type1, 2)
        self.assertEqual(spawned[0].type2, 0)
        self.assertEqual((int(spawned[0].x), int(spawned[0].y)), (70, 90))
        self.assertEqual(spawned[1].type1, 0)
        self.assertEqual(spawned[1].type2, 3)

    def test_spawn_crates_expands_counts_when_positions_missing(self) -> None:
        crate_counts = CrateCounts(
            weapon_crates=(2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            bullet_crates=(1, 0, 0, 0, 0, 0, 0, 0, 0),
            energy_crates=1,
        )
        level = _build_level(width=12, height=12, normal_crate_counts=crate_counts)

        spawned = spawn_crates_for_level(level, player_x=40.0, player_y=40.0)

        self.assertEqual(len(spawned), 4)
        self.assertEqual(sum(1 for crate in spawned if crate.type1 == 0), 2)
        self.assertEqual(sum(1 for crate in spawned if crate.type1 == 1), 1)
        self.assertEqual(sum(1 for crate in spawned if crate.type1 == 2), 1)

    def test_crate_effect_progression_and_alive_count(self) -> None:
        crates = [
            CrateState(
                crate_id=0,
                type1=0,
                type2=0,
                x=30.0,
                y=30.0,
                health=0.0,
                max_health=12.0,
                alive=False,
            ),
            CrateState(
                crate_id=1,
                type1=1,
                type2=0,
                x=50.0,
                y=50.0,
                health=8.0,
                max_health=12.0,
                hit_flash_ticks=2,
            ),
        ]

        self.assertEqual(alive_crate_count(crates), 1)
        advance_crate_effects(crates)
        self.assertEqual(crates[1].hit_flash_ticks, 1)

    def test_collect_weapon_crate_grants_slot_and_removes_crate(self) -> None:
        player = PlayerState(x=40.0, y=40.0)
        crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=47.0,
            y=47.0,
            health=12.0,
            max_health=12.0,
        )

        report = collect_crates_for_player([crate], player)

        self.assertEqual(report.crates_collected, 1)
        self.assertEqual(report.weapons_granted, 1)
        self.assertTrue(player.weapons[1])
        self.assertFalse(crate.alive)
        self.assertEqual(crate.health, 0.0)

    def test_collect_weapon_crate_skips_already_owned_weapon(self) -> None:
        player = PlayerState(x=40.0, y=40.0)
        player.grant_weapon(1)
        crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=47.0,
            y=47.0,
            health=12.0,
            max_health=12.0,
        )

        report = collect_crates_for_player([crate], player)

        self.assertEqual(report.crates_collected, 0)
        self.assertEqual(report.weapons_granted, 0)
        self.assertTrue(crate.alive)
        self.assertEqual(crate.health, 12.0)

    def test_collect_bullet_crate_reports_legacy_pack_amount(self) -> None:
        player = PlayerState(x=40.0, y=40.0)
        crate = CrateState(
            crate_id=0,
            type1=1,
            type2=0,
            x=47.0,
            y=47.0,
            health=12.0,
            max_health=12.0,
        )

        report = collect_crates_for_player([crate], player)

        self.assertEqual(report.crates_collected, 1)
        self.assertEqual(report.bullet_packs_collected, 1)
        self.assertEqual(report.bullets_collected, 50)
        self.assertEqual(player.bullets[0], 50)
        self.assertFalse(crate.alive)

    def test_collect_bullet_crate_at_capacity_keeps_crate(self) -> None:
        player = PlayerState(x=40.0, y=40.0)
        player.bullets[0] = 300
        crate = CrateState(
            crate_id=0,
            type1=1,
            type2=0,
            x=47.0,
            y=47.0,
            health=12.0,
            max_health=12.0,
        )

        report = collect_crates_for_player([crate], player)

        self.assertEqual(report.crates_collected, 0)
        self.assertEqual(report.bullets_collected, 0)
        self.assertEqual(player.bullets[0], 300)
        self.assertTrue(crate.alive)

    def test_collect_energy_crate_restores_health_with_cap(self) -> None:
        player = PlayerState(x=40.0, y=40.0, health=70.0)
        crate = CrateState(
            crate_id=0,
            type1=2,
            type2=0,
            x=47.0,
            y=47.0,
            health=12.0,
            max_health=12.0,
        )

        report = collect_crates_for_player([crate], player)

        self.assertEqual(report.crates_collected, 1)
        self.assertEqual(report.energy_collected, 30.0)
        self.assertEqual(player.health, 100.0)
        self.assertFalse(crate.alive)

    def test_collect_energy_crate_uses_shield_bonus_capacity(self) -> None:
        player = PlayerState(x=40.0, y=40.0, health=95.0, shield=2)
        crate = CrateState(
            crate_id=0,
            type1=2,
            type2=0,
            x=47.0,
            y=47.0,
            health=12.0,
            max_health=12.0,
        )

        report = collect_crates_for_player([crate], player)

        self.assertEqual(report.crates_collected, 1)
        self.assertEqual(report.energy_collected, 25.0)
        self.assertEqual(player.health, 120.0)
        self.assertFalse(crate.alive)

    def test_collect_energy_crate_at_full_health_keeps_crate(self) -> None:
        player = PlayerState(x=40.0, y=40.0, health=100.0)
        crate = CrateState(
            crate_id=0,
            type1=2,
            type2=0,
            x=47.0,
            y=47.0,
            health=12.0,
            max_health=12.0,
        )

        report = collect_crates_for_player([crate], player)

        self.assertEqual(report.crates_collected, 0)
        self.assertEqual(report.energy_collected, 0.0)
        self.assertEqual(player.health, 100.0)
        self.assertTrue(crate.alive)

    def test_resolve_shot_applies_damage_when_enemy_hit(self) -> None:
        level = _build_level(height=12)
        enemy = EnemyState(enemy_id=0, type_index=0, x=40.0, y=80.0, health=18.0, max_health=18.0)
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=34,
            weapon_slot=0,
            impact_x=54,
            impact_y=98,
        )

        result = resolve_shot_against_enemies(level, [enemy], shot)

        self.assertEqual(result.enemy_id, 0)
        self.assertEqual(result.damage, 3.0)
        self.assertFalse(result.enemy_killed)
        self.assertEqual(enemy.health, 15.0)
        self.assertTrue(enemy.alive)
        self.assertEqual((result.impact_x, result.impact_y), (54, 94))

    def test_resolve_shot_can_kill_enemy(self) -> None:
        level = _build_level(height=12)
        enemy = EnemyState(enemy_id=0, type_index=0, x=40.0, y=80.0, health=10.0, max_health=10.0)
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=170,
            weapon_slot=7,
            impact_x=54,
            impact_y=120,
        )

        result = resolve_shot_against_enemies(level, [enemy], shot)

        self.assertEqual(result.enemy_id, 0)
        self.assertTrue(result.enemy_killed)
        self.assertFalse(enemy.alive)
        self.assertEqual(enemy.health, 0.0)

    def test_resolve_shot_hits_crate_before_enemy(self) -> None:
        level = _build_level(height=12)
        enemy = EnemyState(enemy_id=0, type_index=0, x=40.0, y=120.0, health=18.0, max_health=18.0)
        crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=48.0,
            y=84.0,
            health=12.0,
            max_health=12.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=170,
            weapon_slot=1,
            impact_x=54,
            impact_y=130,
        )

        result = resolve_shot_against_enemies(level, [enemy], shot, crates=[crate])

        self.assertIsNone(result.enemy_id)
        self.assertEqual(result.crate_id, 0)
        self.assertFalse(result.crate_destroyed)
        self.assertEqual(enemy.health, 18.0)
        self.assertEqual(crate.health, 7.0)

    def test_resolve_shot_can_destroy_crate(self) -> None:
        level = _build_level(height=12)
        crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=48.0,
            y=84.0,
            health=4.0,
            max_health=12.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=170,
            weapon_slot=1,
            impact_x=54,
            impact_y=130,
        )

        result = resolve_shot_against_enemies(level, [], shot, crates=[crate])

        self.assertEqual(result.crate_id, 0)
        self.assertTrue(result.crate_destroyed)
        self.assertFalse(crate.alive)
        self.assertEqual(crate.health, 0.0)

    def test_resolve_shot_stops_at_wall_before_enemy(self) -> None:
        level = _build_level(height=12, walls={(2, 4)})
        enemy = EnemyState(enemy_id=0, type_index=0, x=40.0, y=120.0, health=18.0, max_health=18.0)
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=170,
            weapon_slot=1,
            impact_x=54,
            impact_y=130,
        )

        result = resolve_shot_against_enemies(level, [enemy], shot)

        self.assertIsNone(result.enemy_id)
        self.assertEqual(enemy.health, 18.0)
        self.assertLess(result.impact_y, 80)

    def test_resolve_shot_corner_graze_wall_blocks_enemy_hit(self) -> None:
        open_level = _build_level(width=12, height=12)
        blocked_level = _build_level(width=12, height=12, walls={(1, 1)})
        shot = ShotEvent(
            origin_x=10.0,
            origin_y=10.0,
            angle=20,
            max_distance=170,
            weapon_slot=1,
            impact_x=0,
            impact_y=0,
        )

        enemy_open = EnemyState(enemy_id=0, type_index=0, x=10.0, y=34.0, health=18.0, max_health=18.0)
        enemy_blocked = EnemyState(enemy_id=0, type_index=0, x=10.0, y=34.0, health=18.0, max_health=18.0)

        open_result = resolve_shot_against_enemies(open_level, [enemy_open], shot)
        blocked_result = resolve_shot_against_enemies(blocked_level, [enemy_blocked], shot)

        self.assertEqual(open_result.enemy_id, 0)
        self.assertEqual(open_result.damage, 5.0)
        self.assertEqual(enemy_open.health, 13.0)

        self.assertIsNone(blocked_result.enemy_id)
        self.assertEqual(enemy_blocked.health, 18.0)

    def test_enemy_effect_progression_and_alive_count(self) -> None:
        enemies = [
            EnemyState(enemy_id=0, type_index=0, x=0.0, y=0.0, health=0.0, max_health=18.0, alive=False),
            EnemyState(enemy_id=1, type_index=1, x=20.0, y=20.0, health=20.0, max_health=28.0, hit_flash_ticks=2),
        ]

        self.assertEqual(alive_enemy_count(enemies), 1)
        advance_enemy_effects(enemies)
        self.assertEqual(enemies[1].hit_flash_ticks, 1)

    def test_enemy_behavior_rotates_and_moves_toward_player(self) -> None:
        level = _build_level(width=12, height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=140.0,
            health=18.0,
            max_health=18.0,
            angle=90,
            target_angle=90,
            load_count=0,
        )

        report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertTrue(enemy.sees_player)
        self.assertEqual(enemy.angle, 99)
        self.assertGreater(enemy.x, 40.0)
        self.assertLess(enemy.y, 140.0)

    def test_enemy_behavior_uses_legacy_los_trace_step(self) -> None:
        level = _build_level(width=12, height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=140.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=0,
        )

        with patch.object(combat_module, "_line_of_sight_clear", return_value=True) as los:
            update_enemy_behavior(level, [enemy], player)

        self.assertTrue(enemy.sees_player)
        self.assertGreaterEqual(los.call_count, 1)
        self.assertEqual(los.call_args.kwargs["step"], combat_module.ENEMY_LINE_OF_SIGHT_TRACE_STEP)
        self.assertEqual(combat_module.ENEMY_LINE_OF_SIGHT_TRACE_STEP, 5)

    def test_enemy_behavior_does_not_detect_player_outside_front_vision_arc(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=0,
            target_angle=0,
            walk_ticks=120,
            load_count=10,
        )

        report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertEqual(report.hits_on_player, 0)
        self.assertEqual(report.damage_to_player, 0.0)
        self.assertFalse(enemy.sees_player)
        self.assertEqual(player.health, 100.0)

    def test_enemy_behavior_does_not_detect_player_beyond_vision_distance(self) -> None:
        level = _build_level(height=20)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=260.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            walk_ticks=120,
            load_count=10,
        )

        report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertEqual(report.hits_on_player, 0)
        self.assertEqual(report.damage_to_player, 0.0)
        self.assertFalse(enemy.sees_player)
        self.assertEqual(player.health, 100.0)

    def test_enemy_behavior_does_not_detect_player_behind_crate_cover(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=10,
        )
        crate = CrateState(
            crate_id=0,
            type1=1,
            type2=0,
            x=47.0,
            y=67.0,
            health=12.0,
            max_health=12.0,
        )

        report = update_enemy_behavior(level, [enemy], player, crates=[crate])

        self.assertEqual(report.shots_fired, 0)
        self.assertEqual(report.hits_on_player, 0)
        self.assertEqual(report.damage_to_player, 0.0)
        self.assertFalse(enemy.sees_player)
        self.assertEqual(player.health, 100.0)

    def test_enemy_hitscan_shot_hits_crate_before_player(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
        )
        crate = CrateState(
            crate_id=0,
            type1=1,
            type2=0,
            x=47.0,
            y=67.0,
            health=5.0,
            max_health=5.0,
        )

        result = combat_module.resolve_enemy_shot_against_player(
            level,
            enemy=enemy,
            player=player,
            weapon_slot=1,
            crates=[crate],
        )

        self.assertFalse(result.player_hit)
        self.assertTrue(result.crate_hit)
        self.assertTrue(result.crate_destroyed)
        self.assertEqual(result.damage, 0.0)
        self.assertEqual(crate.health, 0.0)
        self.assertFalse(crate.alive)
        self.assertEqual(crate.hit_flash_ticks, combat_module.CRATE_FLASH_TICKS)
        self.assertEqual(player.health, 100.0)

    def test_enemy_patrol_idle_without_start_roll_does_not_move(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=120.0,
            y=120.0,
            health=18.0,
            max_health=18.0,
            angle=0,
            target_angle=0,
            walk_ticks=0,
            load_count=0,
        )

        with patch.object(combat_module, "_enemy_next_patrol_roll", return_value=0):
            report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertEqual(enemy.walk_ticks, 0)
        self.assertEqual(enemy.x, 120.0)
        self.assertEqual(enemy.y, 120.0)

    def test_enemy_patrol_start_roll_begins_burst_movement(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=0.0, y=0.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=120.0,
            y=120.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            walk_ticks=0,
            load_count=0,
        )

        with patch.object(combat_module, "_enemy_next_patrol_roll", side_effect=(0, 1, 7)):
            report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertGreater(enemy.walk_ticks, 0)
        self.assertLess(enemy.y, 120.0)

    def test_enemy_patrol_turn_roll_waits_until_target_rotation_completes(self) -> None:
        level = _build_level(height=20)
        player = PlayerState(x=0.0, y=0.0)
        enemy = EnemyState(
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
        )

        with patch.object(combat_module, "_enemy_next_patrol_roll", return_value=1) as patrol_roll:
            report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertEqual(enemy.target_angle, 90)
        self.assertGreater(enemy.angle, 0)
        self.assertLessEqual(enemy.angle, 18)
        self.assertGreater(enemy.walk_ticks, 0)
        self.assertEqual(patrol_roll.call_count, 2)

    def test_enemy_shoot_counter_tracks_attack_window_and_los_break(self) -> None:
        open_level = _build_level(height=12)
        blocked_level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=0,
            shoot_count=0,
        )

        first = update_enemy_behavior(open_level, [enemy], player)
        self.assertEqual(first.shots_fired, 0)
        self.assertTrue(enemy.sees_player)
        self.assertEqual(enemy.shoot_count, 1)

        second = update_enemy_behavior(blocked_level, [enemy], player)
        self.assertEqual(second.shots_fired, 0)
        self.assertFalse(enemy.sees_player)
        self.assertEqual(enemy.shoot_count, 0)

    def test_enemy_lost_sight_starts_chase_window(self) -> None:
        open_level = _build_level(height=12)
        blocked_level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=0,
            chase_ticks=0,
        )

        first = update_enemy_behavior(open_level, [enemy], player)
        self.assertEqual(first.shots_fired, 0)
        self.assertTrue(enemy.sees_player)
        self.assertEqual(enemy.chase_ticks, 0)

        start_y = enemy.y
        second = update_enemy_behavior(blocked_level, [enemy], player)
        self.assertEqual(second.shots_fired, 0)
        self.assertFalse(enemy.sees_player)
        self.assertGreater(enemy.chase_ticks, 0)
        self.assertLess(enemy.y, start_y)

    def test_enemy_without_prior_sight_does_not_start_chase_window(self) -> None:
        blocked_level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=0,
            chase_ticks=0,
        )

        report = update_enemy_behavior(blocked_level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertFalse(enemy.sees_player)
        self.assertEqual(enemy.chase_ticks, 0)

    def test_enemy_explosive_shoot_counter_accumulates_during_reload(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=4,
            x=40.0,
            y=120.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
            load_count=28,
            shoot_count=0,
        )
        projectiles: list[EnemyProjectile] = []

        first = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)
        second = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)
        third = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)

        self.assertEqual(first.shots_fired, 0)
        self.assertEqual(second.shots_fired, 0)
        self.assertEqual(third.shots_fired, 1)
        self.assertEqual(third.projectiles_spawned, 1)
        self.assertEqual(enemy.shoot_count, 3)
        self.assertEqual(len(projectiles), 1)

    def test_enemy_behavior_shoots_and_hits_player(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=10,
        )

        report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 1)
        self.assertEqual(report.hits_on_player, 1)
        self.assertEqual(report.damage_to_player, 5.0)
        self.assertEqual(player.health, 95.0)
        self.assertEqual(player.hits_taken_total, 1)
        self.assertGreater(player.hit_flash_ticks, 0)

    def test_enemy_behavior_spawns_projectiles_when_buffer_provided(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=10,
        )
        projectiles = []

        report = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)

        self.assertEqual(report.shots_fired, 1)
        self.assertEqual(report.projectiles_spawned, 1)
        self.assertEqual(report.hits_on_player, 0)
        self.assertEqual(report.damage_to_player, 0.0)
        self.assertEqual(player.health, 100.0)
        self.assertEqual(len(projectiles), 1)

    def test_enemy_projectile_travel_time_hits_player(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=120.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=10,
        )
        projectiles = []

        report = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)
        self.assertEqual(report.projectiles_spawned, 1)

        total_hits = 0
        total_damage = 0.0
        for _ in range(10):
            projectile_report = update_enemy_projectiles(level, projectiles, player)
            total_hits += projectile_report.hits_on_player
            total_damage += projectile_report.damage_to_player
            if not projectiles:
                break

        self.assertEqual(total_hits, 1)
        self.assertEqual(total_damage, 5.0)
        self.assertEqual(player.health, 95.0)
        self.assertEqual(len(projectiles), 0)

    def test_enemy_projectile_does_not_apply_damage_when_player_already_dead(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0, health=0.0, dead=True)
        projectiles = [
            EnemyProjectile(
                owner_enemy_id=0,
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
        ]

        report = update_enemy_projectiles(level, projectiles, player)

        self.assertEqual(report.hits_on_player, 0)
        self.assertEqual(report.damage_to_player, 0.0)
        self.assertEqual(player.health, 0.0)
        self.assertEqual(player.hits_taken_total, 0)
        self.assertEqual(len(projectiles), 0)

    def test_enemy_projectile_stops_at_wall_before_player(self) -> None:
        level = _build_level(height=12)
        blocked_level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=10,
        )
        projectiles = []

        report = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)
        self.assertEqual(report.projectiles_spawned, 1)

        total_hits = 0
        total_damage = 0.0
        for _ in range(8):
            projectile_report = update_enemy_projectiles(blocked_level, projectiles, player)
            total_hits += projectile_report.hits_on_player
            total_damage += projectile_report.damage_to_player
            if not projectiles:
                break

        self.assertEqual(total_hits, 0)
        self.assertEqual(total_damage, 0.0)
        self.assertEqual(player.health, 100.0)
        self.assertEqual(len(projectiles), 0)

    def test_enemy_projectile_corner_graze_is_blocked(self) -> None:
        open_level = _build_level(width=10, height=10)
        blocked_level = _build_level(width=10, height=10, walls={(1, 1)})

        enemy_open = EnemyState(
            enemy_id=0,
            type_index=0,
            x=0.0,
            y=0.0,
            health=18.0,
            max_health=18.0,
            angle=0,
            target_angle=0,
            load_count=10,
        )
        enemy_blocked = EnemyState(
            enemy_id=0,
            type_index=0,
            x=0.0,
            y=0.0,
            health=18.0,
            max_health=18.0,
            angle=0,
            target_angle=0,
            load_count=10,
        )
        player_open = PlayerState(x=8.0, y=38.0)
        player_blocked = PlayerState(x=8.0, y=38.0)
        open_projectiles: list = []
        blocked_projectiles: list = []

        open_fire = update_enemy_behavior(open_level, [enemy_open], player_open, enemy_projectiles=open_projectiles)
        blocked_fire = update_enemy_behavior(
            blocked_level,
            [enemy_blocked],
            player_blocked,
            enemy_projectiles=blocked_projectiles,
        )

        self.assertEqual(open_fire.shots_fired, 1)
        self.assertEqual(blocked_fire.shots_fired, 1)
        self.assertEqual(open_fire.projectiles_spawned, 1)
        self.assertEqual(blocked_fire.projectiles_spawned, 1)

        open_hits = 0
        open_damage = 0.0
        for _ in range(12):
            if not open_projectiles:
                break
            report = update_enemy_projectiles(open_level, open_projectiles, player_open)
            open_hits += report.hits_on_player
            open_damage += report.damage_to_player

        blocked_hits = 0
        blocked_damage = 0.0
        for _ in range(12):
            if not blocked_projectiles:
                break
            report = update_enemy_projectiles(blocked_level, blocked_projectiles, player_blocked)
            blocked_hits += report.hits_on_player
            blocked_damage += report.damage_to_player

        self.assertEqual(open_hits, 1)
        self.assertEqual(open_damage, 5.0)
        self.assertEqual(blocked_hits, 0)
        self.assertEqual(blocked_damage, 0.0)
        self.assertEqual(player_blocked.health, 100.0)

    def test_enemy_projectile_hits_crate_before_player(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=120.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=10,
        )
        crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=48.0,
            y=84.0,
            health=12.0,
            max_health=12.0,
        )
        projectiles = []

        report = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)
        self.assertEqual(report.projectiles_spawned, 1)

        total_hits = 0
        total_damage = 0.0
        total_crate_hits = 0
        for _ in range(10):
            projectile_report = update_enemy_projectiles(level, projectiles, player, crates=[crate])
            total_hits += projectile_report.hits_on_player
            total_damage += projectile_report.damage_to_player
            total_crate_hits += projectile_report.crates_hit
            if not projectiles:
                break

        self.assertEqual(total_hits, 0)
        self.assertEqual(total_damage, 0.0)
        self.assertEqual(total_crate_hits, 1)
        self.assertEqual(player.health, 100.0)
        self.assertEqual(crate.health, 7.0)
        self.assertTrue(crate.alive)

    def test_enemy_shotgun_attack_can_hit_with_multiple_pellets(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=1,
            x=40.0,
            y=80.0,
            health=28.0,
            max_health=28.0,
            angle=180,
            target_angle=180,
            load_count=17,
        )

        report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 1)
        self.assertEqual(report.hits_on_player, 6)
        self.assertEqual(report.damage_to_player, 18.0)
        self.assertEqual(player.health, 82.0)

    def test_enemy_shotgun_projectiles_hit_with_travel_time(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=1,
            x=40.0,
            y=80.0,
            health=28.0,
            max_health=28.0,
            angle=180,
            target_angle=180,
            load_count=17,
        )
        projectiles = []

        report = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)

        self.assertEqual(report.shots_fired, 1)
        self.assertEqual(report.projectiles_spawned, 6)
        self.assertEqual(report.hits_on_player, 0)
        self.assertEqual(report.damage_to_player, 0.0)

        total_hits = 0
        total_damage = 0.0
        for _ in range(8):
            projectile_report = update_enemy_projectiles(level, projectiles, player)
            total_hits += projectile_report.hits_on_player
            total_damage += projectile_report.damage_to_player
            if not projectiles:
                break

        self.assertEqual(total_hits, 6)
        self.assertEqual(total_damage, 18.0)
        self.assertEqual(player.health, 82.0)

    def test_enemy_shotgun_corner_graze_wall_reduces_pellet_hits(self) -> None:
        open_level = _build_level(width=10, height=10)
        blocked_level = _build_level(width=10, height=10, walls={(2, 3)})

        player_open = PlayerState(x=20.0, y=90.0)
        player_blocked = PlayerState(x=20.0, y=90.0)
        enemy_open = EnemyState(
            enemy_id=0,
            type_index=1,
            x=20.0,
            y=20.0,
            health=28.0,
            max_health=28.0,
            angle=0,
            target_angle=0,
            load_count=17,
        )
        enemy_blocked = EnemyState(
            enemy_id=0,
            type_index=1,
            x=20.0,
            y=20.0,
            health=28.0,
            max_health=28.0,
            angle=0,
            target_angle=0,
            load_count=17,
        )

        open_report = update_enemy_behavior(open_level, [enemy_open], player_open)
        blocked_report = update_enemy_behavior(blocked_level, [enemy_blocked], player_blocked)

        self.assertEqual(open_report.shots_fired, 1)
        self.assertEqual(blocked_report.shots_fired, 1)
        self.assertGreater(open_report.hits_on_player, blocked_report.hits_on_player)
        self.assertGreater(open_report.damage_to_player, blocked_report.damage_to_player)

    def test_enemy_direct_shot_corner_graze_blocks_fire_with_legacy_los_step(self) -> None:
        open_level = _build_level(width=10, height=10)
        blocked_level = _build_level(width=10, height=10, walls={(1, 1)})

        player_open = PlayerState(x=24.0, y=38.0)
        player_blocked = PlayerState(x=24.0, y=38.0)
        enemy_open = EnemyState(
            enemy_id=0,
            type_index=5,
            x=28.0,
            y=10.0,
            health=10.0,
            max_health=10.0,
            angle=352,
            target_angle=352,
            load_count=10,
        )
        enemy_blocked = EnemyState(
            enemy_id=0,
            type_index=5,
            x=28.0,
            y=10.0,
            health=10.0,
            max_health=10.0,
            angle=352,
            target_angle=352,
            load_count=10,
        )

        open_report = update_enemy_behavior(open_level, [enemy_open], player_open)
        blocked_report = update_enemy_behavior(blocked_level, [enemy_blocked], player_blocked)

        self.assertEqual(open_report.shots_fired, 1)
        self.assertEqual(open_report.hits_on_player, 1)
        self.assertEqual(open_report.damage_to_player, 3.0)

        self.assertEqual(blocked_report.shots_fired, 0)
        self.assertEqual(blocked_report.hits_on_player, 0)
        self.assertEqual(blocked_report.damage_to_player, 0.0)
        self.assertEqual(player_blocked.health, 100.0)
        self.assertFalse(enemy_blocked.sees_player)

    def test_dead_player_no_longer_receives_enemy_fire(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0, health=4.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=10,
        )

        first = update_enemy_behavior(level, [enemy], player)
        self.assertEqual(first.shots_fired, 1)
        self.assertEqual(first.hits_on_player, 1)
        self.assertTrue(player.dead)

        enemy.load_count = 10
        second = update_enemy_behavior(level, [enemy], player)
        self.assertEqual(second.shots_fired, 0)
        self.assertEqual(second.hits_on_player, 0)
        self.assertEqual(second.damage_to_player, 0.0)

    def test_enemy_explosive_weapon_holds_fire_at_point_blank_distance(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=72.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=4,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
            load_count=30,
        )

        report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertEqual(report.hits_on_player, 0)
        self.assertEqual(report.damage_to_player, 0.0)
        self.assertEqual(player.health, 100.0)

    def test_enemy_explosive_long_range_shot_starts_forward_pressure(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=4,
            x=40.0,
            y=120.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
            load_count=30,
        )
        projectiles: list[EnemyProjectile] = []

        first = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)
        self.assertEqual(first.shots_fired, 1)
        self.assertGreaterEqual(enemy.pressure_ticks, 1)

        start_x = enemy.x
        start_y = enemy.y
        second = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)

        self.assertEqual(second.shots_fired, 0)
        self.assertLess(enemy.y, start_y)
        self.assertLessEqual(abs(enemy.x - start_x), abs(enemy.y - start_y))

    def test_enemy_explosive_pressure_resets_when_line_of_sight_breaks(self) -> None:
        open_level = _build_level(height=12)
        blocked_level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=4,
            x=40.0,
            y=120.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
            load_count=30,
        )

        first = update_enemy_behavior(open_level, [enemy], player)
        self.assertEqual(first.shots_fired, 1)
        self.assertGreater(enemy.pressure_ticks, 0)

        second = update_enemy_behavior(blocked_level, [enemy], player)
        self.assertEqual(second.shots_fired, 0)
        self.assertFalse(enemy.sees_player)
        self.assertEqual(enemy.pressure_ticks, 0)

    def test_enemy_strafe_direction_holds_across_short_reload_windows(self) -> None:
        enemy = EnemyState(
            enemy_id=3,
            type_index=2,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
            shoot_count=5,
        )

        hold_ticks = max(1, combat_module.ENEMY_STRAFE_DIRECTION_HOLD_TICKS)
        stagger_window = max(0, combat_module.ENEMY_STRAFE_RELOAD_STAGGER_TICKS)
        phase_delay = 0
        if stagger_window > 0:
            phase_delay = (enemy.enemy_id + enemy.type_index) % (stagger_window + 1)

        first_block: list[int] = []
        for strafe_tick in range(phase_delay, phase_delay + hold_ticks):
            enemy.strafe_ticks = strafe_tick
            first_block.append(combat_module._enemy_strafe_angle(enemy))

        self.assertTrue(all(angle == first_block[0] for angle in first_block))

        enemy.strafe_ticks = phase_delay + hold_ticks
        second_block_angle = combat_module._enemy_strafe_angle(enemy)
        self.assertIn(second_block_angle, ((enemy.angle + 90) % 360, (enemy.angle + 270) % 360))
        self.assertNotEqual(second_block_angle, first_block[0])

    def test_enemy_strafe_direction_is_stable_across_shoot_count_changes(self) -> None:
        enemy = EnemyState(
            enemy_id=1,
            type_index=2,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
            load_count=2,
            strafe_ticks=2,
            shoot_count=0,
        )

        first_angle = combat_module._enemy_strafe_angle(enemy)
        enemy.shoot_count = 7
        second_angle = combat_module._enemy_strafe_angle(enemy)

        self.assertEqual(first_angle, second_angle)

    def test_enemy_strafe_switch_tick_is_staggered_between_neighbor_enemy_ids(self) -> None:
        hold_ticks = max(1, combat_module.ENEMY_STRAFE_DIRECTION_HOLD_TICKS)

        first_enemy = EnemyState(
            enemy_id=0,
            type_index=2,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
        )
        second_enemy = EnemyState(
            enemy_id=1,
            type_index=2,
            x=80.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
        )

        def first_switch_tick(enemy: EnemyState) -> int | None:
            enemy.strafe_ticks = 0
            previous_angle = combat_module._enemy_strafe_angle(enemy)
            for strafe_tick in range(1, hold_ticks * 3):
                enemy.strafe_ticks = strafe_tick
                angle = combat_module._enemy_strafe_angle(enemy)
                if angle != previous_angle:
                    return strafe_tick
            return None

        first_switch = first_switch_tick(first_enemy)
        second_switch = first_switch_tick(second_enemy)

        self.assertIsNotNone(first_switch)
        self.assertIsNotNone(second_switch)
        assert first_switch is not None
        assert second_switch is not None
        self.assertNotEqual(first_switch, second_switch)
        self.assertGreater(second_switch, first_switch)

    def test_enemy_strafe_retries_opposite_direction_when_primary_lane_is_blocked(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=2,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
            load_count=1,
            shoot_count=0,
        )

        with patch.object(combat_module, "_enemy_strafe_angle", return_value=90), patch.object(
            combat_module,
            "_move_enemy_with_collision",
            side_effect=(False, True),
        ) as move_enemy:
            report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertEqual(move_enemy.call_count, 2)

        first_call = move_enemy.call_args_list[0]
        second_call = move_enemy.call_args_list[1]
        self.assertEqual(first_call.kwargs["angle"], 90)
        self.assertEqual(second_call.kwargs["angle"], 270)

    def test_grenade_near_miss_applies_splash_damage(self) -> None:
        level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=20.0, y=64.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=4,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
        )

        attack = resolve_enemy_attack_against_player(
            level,
            enemy=enemy,
            player=player,
            weapon_slot=5,
        )

        self.assertEqual(attack.hit_count, 1)
        self.assertGreater(attack.total_damage, 0.0)
        self.assertLess(attack.total_damage, 20.0)
        self.assertLess(player.health, 100.0)

    def test_grenade_near_miss_is_fully_blocked_by_wall_fan(self) -> None:
        level = _build_level(height=12, walls={(2, 3), (3, 3)})
        player = PlayerState(x=44.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=4,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
        )

        attack = resolve_enemy_attack_against_player(
            level,
            enemy=enemy,
            player=player,
            weapon_slot=5,
        )

        self.assertEqual(attack.hit_count, 0)
        self.assertEqual(attack.total_damage, 0.0)
        self.assertEqual(player.health, 100.0)

    def test_grenade_near_miss_splash_is_reduced_by_crate_cover(self) -> None:
        level = _build_level(height=12, walls={(2, 3)})
        player_open = PlayerState(x=20.0, y=64.0)
        player_cover = PlayerState(x=20.0, y=64.0)
        enemy_open = EnemyState(
            enemy_id=0,
            type_index=4,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
        )
        enemy_cover = EnemyState(
            enemy_id=0,
            type_index=4,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
        )
        cover_crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=22.0,
            y=69.0,
            health=12.0,
            max_health=12.0,
        )

        open_attack = resolve_enemy_attack_against_player(
            level,
            enemy=enemy_open,
            player=player_open,
            weapon_slot=5,
        )
        cover_attack = resolve_enemy_attack_against_player(
            level,
            enemy=enemy_cover,
            player=player_cover,
            weapon_slot=5,
            crates=[cover_crate],
        )

        self.assertGreater(open_attack.total_damage, 0.0)
        self.assertGreaterEqual(open_attack.hit_count, 1)
        self.assertLess(cover_attack.total_damage, open_attack.total_damage)
        self.assertGreater(player_cover.health, player_open.health)

    def test_grenade_projectile_near_miss_applies_splash_damage(self) -> None:
        level = _build_level(height=12)
        blocked_level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=40.0, y=68.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=4,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
            load_count=30,
        )
        projectiles = []

        report = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)
        self.assertEqual(report.projectiles_spawned, 1)

        total_damage = 0.0
        total_hits = 0
        for _ in range(10):
            projectile_report = update_enemy_projectiles(blocked_level, projectiles, player)
            total_hits += projectile_report.hits_on_player
            total_damage += projectile_report.damage_to_player
            if not projectiles:
                break

        self.assertEqual(total_hits, 1)
        self.assertGreater(total_damage, 0.0)
        self.assertLess(total_damage, 20.0)
        self.assertLess(player.health, 100.0)

    def test_projectile_splash_hits_player_collision_edge_not_only_center(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        projectiles = [
            EnemyProjectile(
                owner_enemy_id=0,
                weapon_slot=5,
                x=67.0,
                y=54.0,
                vx=0.0,
                vy=0.0,
                speed=0.0,
                damage=20.0,
                remaining_ticks=1,
                radius=0,
                splash_radius=10,
            ),
        ]

        report = update_enemy_projectiles(level, projectiles, player)

        self.assertEqual(report.hits_on_player, 1)
        self.assertGreater(report.damage_to_player, 0.0)
        self.assertLess(report.damage_to_player, 20.0)
        self.assertEqual(len(projectiles), 0)
        self.assertLess(player.health, 100.0)

    def test_grenade_projectile_near_miss_is_fully_blocked_by_wall_fan(self) -> None:
        level = _build_level(height=12)
        blocked_level = _build_level(height=12, walls={(2, 3), (2, 4)})
        player = PlayerState(x=40.0, y=68.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=4,
            x=40.0,
            y=80.0,
            health=40.0,
            max_health=40.0,
            angle=180,
            target_angle=180,
            load_count=30,
        )
        projectiles = []

        report = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)
        self.assertEqual(report.projectiles_spawned, 1)

        total_damage = 0.0
        total_hits = 0
        for _ in range(10):
            projectile_report = update_enemy_projectiles(blocked_level, projectiles, player)
            total_hits += projectile_report.hits_on_player
            total_damage += projectile_report.damage_to_player
            if not projectiles:
                break

        self.assertEqual(total_hits, 0)
        self.assertEqual(total_damage, 0.0)
        self.assertEqual(player.health, 100.0)

    def test_grenade_projectile_wall_impact_splash_is_reduced_by_crate_cover(self) -> None:
        level = _build_level(height=12, walls={(2, 3)})
        player_open = PlayerState(x=40.0, y=68.0)
        player_cover = PlayerState(x=40.0, y=68.0)
        cover_crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=38.0,
            y=71.0,
            health=12.0,
            max_health=12.0,
        )

        open_projectiles = [
            EnemyProjectile(
                owner_enemy_id=0,
                weapon_slot=5,
                x=54.0,
                y=84.0,
                vx=0.0,
                vy=-1.0,
                speed=8.0,
                damage=20.0,
                remaining_ticks=8,
                radius=3,
                splash_radius=48,
            ),
        ]
        cover_projectiles = [
            EnemyProjectile(
                owner_enemy_id=0,
                weapon_slot=5,
                x=54.0,
                y=84.0,
                vx=0.0,
                vy=-1.0,
                speed=8.0,
                damage=20.0,
                remaining_ticks=8,
                radius=3,
                splash_radius=48,
            ),
        ]

        open_hits = 0
        open_damage = 0.0
        for _ in range(10):
            report = update_enemy_projectiles(level, open_projectiles, player_open)
            open_hits += report.hits_on_player
            open_damage += report.damage_to_player
            if not open_projectiles:
                break

        cover_hits = 0
        cover_damage = 0.0
        for _ in range(10):
            report = update_enemy_projectiles(
                level,
                cover_projectiles,
                player_cover,
                crates=[cover_crate],
            )
            cover_hits += report.hits_on_player
            cover_damage += report.damage_to_player
            if not cover_projectiles:
                break

        self.assertGreaterEqual(open_hits, 1)
        self.assertGreater(open_damage, 0.0)
        self.assertLess(cover_damage, open_damage)
        self.assertGreater(player_cover.health, player_open.health)

    def test_grenade_projectile_expiry_splash_is_reduced_by_crate_cover(self) -> None:
        level = _build_level(height=12)
        player_open = PlayerState(x=40.0, y=68.0)
        player_cover = PlayerState(x=40.0, y=68.0)
        cover_crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=43.0,
            y=73.0,
            health=12.0,
            max_health=12.0,
        )

        open_projectiles = [
            EnemyProjectile(
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
        ]
        cover_projectiles = [
            EnemyProjectile(
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
        ]

        open_report = update_enemy_projectiles(level, open_projectiles, player_open)
        cover_report = update_enemy_projectiles(
            level,
            cover_projectiles,
            player_cover,
            crates=[cover_crate],
        )

        self.assertEqual(open_report.hits_on_player, 1)
        self.assertEqual(cover_report.hits_on_player, 1)
        self.assertGreater(open_report.damage_to_player, 0.0)
        self.assertLess(cover_report.damage_to_player, open_report.damage_to_player)
        self.assertGreater(player_cover.health, player_open.health)

    def test_grenade_projectile_wall_impact_splash_can_damage_nearby_crate(self) -> None:
        level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=40.0, y=40.0)
        crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=68.0,
            y=68.0,
            health=12.0,
            max_health=12.0,
        )
        projectiles = [
            EnemyProjectile(
                owner_enemy_id=0,
                weapon_slot=5,
                x=54.0,
                y=84.0,
                vx=0.0,
                vy=-1.0,
                speed=8.0,
                damage=20.0,
                remaining_ticks=8,
                radius=3,
                splash_radius=48,
            ),
        ]

        total_crate_hits = 0
        for _ in range(10):
            projectile_report = update_enemy_projectiles(level, projectiles, player, crates=[crate])
            total_crate_hits += projectile_report.crates_hit
            if not projectiles:
                break

        self.assertGreaterEqual(total_crate_hits, 1)
        self.assertLess(crate.health, 12.0)

    def test_enemy_flamer_deals_low_tick_damage(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=7,
            x=40.0,
            y=80.0,
            health=100.0,
            max_health=100.0,
            angle=180,
            target_angle=180,
            load_count=1,
        )

        report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 1)
        self.assertEqual(report.hits_on_player, 1)
        self.assertAlmostEqual(report.damage_to_player, 0.4)
        self.assertAlmostEqual(player.health, 99.6)

    def test_enemy_flamer_projectile_deals_low_tick_damage(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=7,
            x=40.0,
            y=80.0,
            health=100.0,
            max_health=100.0,
            angle=180,
            target_angle=180,
            load_count=1,
        )
        projectiles = []

        report = update_enemy_behavior(level, [enemy], player, enemy_projectiles=projectiles)
        self.assertEqual(report.projectiles_spawned, 1)

        total_damage = 0.0
        total_hits = 0
        for _ in range(30):
            projectile_report = update_enemy_projectiles(level, projectiles, player)
            total_hits += projectile_report.hits_on_player
            total_damage += projectile_report.damage_to_player
            if total_hits > 0:
                break

        self.assertEqual(total_hits, 1)
        self.assertAlmostEqual(total_damage, 0.4)
        self.assertAlmostEqual(player.health, 99.6)

    def test_player_explosive_slot_detection_and_deploy_defaults(self) -> None:
        c4_shot = ShotEvent(
            origin_x=60.0,
            origin_y=60.0,
            angle=0,
            max_distance=34,
            weapon_slot=9,
            impact_x=60,
            impact_y=94,
        )
        mine_shot = ShotEvent(
            origin_x=80.0,
            origin_y=80.0,
            angle=180,
            max_distance=34,
            weapon_slot=11,
            impact_x=80,
            impact_y=46,
        )

        self.assertTrue(is_player_explosive_weapon_slot(9))
        self.assertTrue(is_player_explosive_weapon_slot(11))
        self.assertFalse(is_player_explosive_weapon_slot(1))

        c4 = deploy_player_explosive_from_shot(c4_shot)
        mine = deploy_player_explosive_from_shot(mine_shot)
        self.assertIsNotNone(c4)
        self.assertIsNotNone(mine)

        assert c4 is not None
        assert mine is not None
        self.assertEqual(c4.kind, "c4")
        self.assertEqual(c4.fuse_ticks, 100)
        self.assertEqual(c4.arming_ticks, 0)
        self.assertEqual(c4.radius, 80)
        self.assertAlmostEqual(c4.falloff_exponent, 1.05)

        self.assertEqual(mine.kind, "mine")
        self.assertEqual(mine.fuse_ticks, 2000)
        self.assertEqual(mine.arming_ticks, 26)
        self.assertEqual(mine.radius, 20)
        self.assertAlmostEqual(mine.falloff_exponent, 1.1)
        self.assertEqual(mine.trigger_radius, 14)

    def test_player_c4_fuse_explosion_damages_enemy_and_crate(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
        )
        crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=20.0,
            y=60.0,
            health=12.0,
            max_health=12.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=94.0,
            angle=0,
            max_distance=34,
            weapon_slot=9,
            impact_x=54,
            impact_y=128,
        )

        explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(explosive)
        assert explosive is not None
        explosive.fuse_ticks = 1

        explosives = [explosive]
        report = update_player_explosives(
            explosives,
            [enemy],
            player,
            level=level,
            crates=[crate],
        )

        self.assertEqual(report.detonations, 1)
        self.assertGreaterEqual(report.enemies_hit, 1)
        self.assertGreaterEqual(report.enemies_killed, 1)
        self.assertGreaterEqual(report.crates_hit, 1)
        self.assertGreaterEqual(report.crates_destroyed, 1)
        self.assertEqual(len(explosives), 0)
        self.assertFalse(enemy.alive)
        self.assertFalse(crate.alive)

    def test_player_c4_explosion_is_blocked_by_wall(self) -> None:
        level = _build_level(height=12, walls={(2, 5), (3, 5)})
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=120.0,
            health=18.0,
            max_health=18.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=94.0,
            angle=0,
            max_distance=34,
            weapon_slot=9,
            impact_x=54,
            impact_y=128,
        )

        explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(explosive)
        assert explosive is not None
        explosive.fuse_ticks = 1

        explosives = [explosive]
        report = update_player_explosives(
            explosives,
            [enemy],
            player,
            level=level,
        )

        self.assertEqual(report.detonations, 1)
        self.assertEqual(report.enemies_hit, 0)
        self.assertEqual(report.enemies_killed, 0)
        self.assertEqual(enemy.health, 18.0)
        self.assertTrue(enemy.alive)

    def test_player_c4_explosion_partial_cover_reduces_damage(self) -> None:
        open_level = _build_level(height=12)
        partial_cover_level = _build_level(height=12, walls={(2, 7)})
        player = PlayerState(x=40.0, y=40.0)
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=94.0,
            angle=0,
            max_distance=34,
            weapon_slot=9,
            impact_x=54,
            impact_y=128,
        )

        enemy_open = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=140.0,
            health=18.0,
            max_health=18.0,
        )
        enemy_partial = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=140.0,
            health=18.0,
            max_health=18.0,
        )

        explosive_open = deploy_player_explosive_from_shot(shot)
        explosive_partial = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(explosive_open)
        self.assertIsNotNone(explosive_partial)
        assert explosive_open is not None
        assert explosive_partial is not None
        explosive_open.fuse_ticks = 1
        explosive_partial.fuse_ticks = 1

        open_report = update_player_explosives(
            [explosive_open],
            [enemy_open],
            player,
            level=open_level,
        )
        partial_report = update_player_explosives(
            [explosive_partial],
            [enemy_partial],
            player,
            level=partial_cover_level,
        )

        self.assertEqual(open_report.enemies_hit, 1)
        self.assertEqual(partial_report.enemies_hit, 1)

        open_damage = 18.0 - enemy_open.health
        partial_damage = 18.0 - enemy_partial.health
        self.assertGreater(open_damage, 0.0)
        self.assertGreater(partial_damage, 0.0)
        self.assertLess(partial_damage, open_damage)
        self.assertTrue(enemy_partial.alive)

    def test_player_c4_center_obstruction_reduces_more_than_side_obstruction(self) -> None:
        center_block_level = _build_level(height=12, walls={(2, 7)})
        side_block_level = _build_level(height=12, walls={(3, 7)})
        player = PlayerState(x=40.0, y=40.0)
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=94.0,
            angle=0,
            max_distance=34,
            weapon_slot=9,
            impact_x=54,
            impact_y=128,
        )

        center_enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=140.0,
            health=18.0,
            max_health=18.0,
        )
        side_enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=140.0,
            health=18.0,
            max_health=18.0,
        )

        center_explosive = deploy_player_explosive_from_shot(shot)
        side_explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(center_explosive)
        self.assertIsNotNone(side_explosive)
        assert center_explosive is not None
        assert side_explosive is not None
        center_explosive.fuse_ticks = 1
        side_explosive.fuse_ticks = 1

        center_report = update_player_explosives(
            [center_explosive],
            [center_enemy],
            player,
            level=center_block_level,
        )
        side_report = update_player_explosives(
            [side_explosive],
            [side_enemy],
            player,
            level=side_block_level,
        )

        self.assertEqual(center_report.enemies_hit, 1)
        self.assertEqual(side_report.enemies_hit, 1)
        center_damage = 18.0 - center_enemy.health
        side_damage = 18.0 - side_enemy.health
        self.assertGreater(side_damage, center_damage)

    def test_player_c4_diagonal_corner_graze_is_heavily_damped(self) -> None:
        open_level = _build_level(height=12)
        diagonal_corner_level = _build_level(height=12, walls={(3, 5)})
        player = PlayerState(x=0.0, y=0.0)
        shot = ShotEvent(
            origin_x=88.0,
            origin_y=117.0,
            angle=0,
            max_distance=34,
            weapon_slot=9,
            impact_x=88,
            impact_y=151,
        )

        enemy_open = EnemyState(
            enemy_id=0,
            type_index=0,
            x=34.0,
            y=50.0,
            health=18.0,
            max_health=18.0,
        )
        enemy_graze = EnemyState(
            enemy_id=0,
            type_index=0,
            x=34.0,
            y=50.0,
            health=18.0,
            max_health=18.0,
        )

        explosive_open = deploy_player_explosive_from_shot(shot)
        explosive_graze = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(explosive_open)
        self.assertIsNotNone(explosive_graze)
        assert explosive_open is not None
        assert explosive_graze is not None
        explosive_open.fuse_ticks = 1
        explosive_graze.fuse_ticks = 1

        open_report = update_player_explosives(
            [explosive_open],
            [enemy_open],
            player,
            level=open_level,
        )
        graze_report = update_player_explosives(
            [explosive_graze],
            [enemy_graze],
            player,
            level=diagonal_corner_level,
        )

        self.assertEqual(open_report.enemies_hit, 1)
        self.assertEqual(graze_report.enemies_hit, 1)
        open_damage = 18.0 - enemy_open.health
        graze_damage = 18.0 - enemy_graze.health
        self.assertGreater(open_damage, 0.0)
        self.assertGreater(graze_damage, 0.0)
        self.assertLess(graze_damage, open_damage * 0.2)

    def test_player_c4_splash_respects_crate_cover_in_tight_corridor(self) -> None:
        level = _build_level(height=12, walls={(2, 6), (3, 6), (4, 6)})
        open_player = PlayerState(x=0.0, y=0.0)
        cover_player = PlayerState(x=0.0, y=0.0)
        enemy_open = EnemyState(
            enemy_id=0,
            type_index=0,
            x=30.0,
            y=100.0,
            health=18.0,
            max_health=18.0,
        )
        enemy_cover = EnemyState(
            enemy_id=0,
            type_index=0,
            x=30.0,
            y=100.0,
            health=18.0,
            max_health=18.0,
        )
        cover_crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=36.0,
            y=104.0,
            health=12.0,
            max_health=12.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=94.0,
            angle=0,
            max_distance=34,
            weapon_slot=9,
            impact_x=54,
            impact_y=128,
        )

        open_explosive = deploy_player_explosive_from_shot(shot)
        cover_explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(open_explosive)
        self.assertIsNotNone(cover_explosive)
        assert open_explosive is not None
        assert cover_explosive is not None
        open_explosive.fuse_ticks = 1
        cover_explosive.fuse_ticks = 1

        open_report = update_player_explosives(
            [open_explosive],
            [enemy_open],
            open_player,
            level=level,
        )
        cover_report = update_player_explosives(
            [cover_explosive],
            [enemy_cover],
            cover_player,
            level=level,
            crates=[cover_crate],
        )

        self.assertEqual(open_report.enemies_hit, 1)
        self.assertEqual(cover_report.enemies_hit, 0)
        self.assertLess(enemy_open.health, enemy_cover.health)
        self.assertEqual(enemy_cover.health, enemy_cover.max_health)
        self.assertFalse(cover_crate.alive)

    def test_player_mine_arms_then_triggers_on_enemy_contact(self) -> None:
        player = PlayerState(x=0.0, y=0.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=80.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
        )
        shot = ShotEvent(
            origin_x=enemy.center_x,
            origin_y=enemy.center_y,
            angle=0,
            max_distance=34,
            weapon_slot=11,
            impact_x=int(enemy.center_x),
            impact_y=int(enemy.center_y),
        )

        explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(explosive)
        assert explosive is not None

        explosives = [explosive]
        for _ in range(25):
            report = update_player_explosives(explosives, [enemy], player)
            self.assertEqual(report.detonations, 0)
            self.assertEqual(len(explosives), 1)

        report = update_player_explosives(explosives, [enemy], player)
        self.assertEqual(report.detonations, 1)
        self.assertEqual(report.enemies_hit, 1)
        self.assertEqual(report.enemies_killed, 1)
        self.assertEqual(len(explosives), 0)
        self.assertFalse(enemy.alive)

    def test_player_mine_trigger_uses_enemy_collision_bounds_not_only_center(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=0.0, y=0.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=60.0,
            y=50.0,
            health=18.0,
            max_health=18.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=34,
            weapon_slot=11,
            impact_x=54,
            impact_y=98,
        )

        explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(explosive)
        assert explosive is not None

        self.assertGreater(math.hypot(enemy.center_x - explosive.x, enemy.center_y - explosive.y), 14.0)
        explosive.arming_ticks = 1
        explosive.fuse_ticks = 5
        explosive.trigger_radius = 14

        explosives = [explosive]
        report = update_player_explosives(
            explosives,
            [enemy],
            player,
            level=level,
        )

        self.assertEqual(report.detonations, 1)
        self.assertEqual(len(explosives), 0)

    def test_player_mine_trigger_uses_blast_center_anchor_for_proximity(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=0.0, y=0.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=58.0,
            health=18.0,
            max_health=18.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=34,
            weapon_slot=11,
            impact_x=54,
            impact_y=98,
        )

        explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(explosive)
        assert explosive is not None

        explosive.arming_ticks = 1
        explosive.fuse_ticks = 5
        explosive.trigger_radius = 14

        explosives = [explosive]
        report = update_player_explosives(
            explosives,
            [enemy],
            player,
            level=level,
        )

        self.assertEqual(report.detonations, 1)
        self.assertEqual(len(explosives), 0)

    def test_player_mine_trigger_allows_near_partial_corner_contact(self) -> None:
        level = _build_level(width=8, height=8, walls={(3, 2)})
        player = PlayerState(x=0.0, y=0.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=56.0,
            y=54.0,
            health=18.0,
            max_health=18.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=34,
            weapon_slot=11,
            impact_x=54,
            impact_y=98,
        )

        explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(explosive)
        assert explosive is not None

        explosive.arming_ticks = 1
        explosive.fuse_ticks = 5
        explosive.trigger_radius = 14

        explosives = [explosive]
        report = update_player_explosives(
            explosives,
            [enemy],
            player,
            level=level,
        )

        self.assertEqual(report.detonations, 1)
        self.assertEqual(len(explosives), 0)

    def test_player_mine_trigger_keeps_far_partial_corner_contact_blocked(self) -> None:
        level = _build_level(width=8, height=8, walls={(3, 2)})
        player = PlayerState(x=0.0, y=0.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=56.0,
            y=32.0,
            health=18.0,
            max_health=18.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=34,
            weapon_slot=11,
            impact_x=54,
            impact_y=98,
        )

        explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(explosive)
        assert explosive is not None

        explosive.arming_ticks = 1
        explosive.fuse_ticks = 5
        explosive.trigger_radius = 14

        explosives = [explosive]
        report = update_player_explosives(
            explosives,
            [enemy],
            player,
            level=level,
        )

        self.assertEqual(report.detonations, 0)
        self.assertEqual(len(explosives), 1)

    def test_player_mine_proximity_trigger_respects_wall_obstruction(self) -> None:
        open_level = _build_level(height=12)
        blocked_level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=0.0, y=0.0)
        enemy_open = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=84.0,
            health=18.0,
            max_health=18.0,
        )
        enemy_blocked = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=84.0,
            health=18.0,
            max_health=18.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=34,
            weapon_slot=11,
            impact_x=54,
            impact_y=98,
        )

        open_explosive = deploy_player_explosive_from_shot(shot)
        blocked_explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(open_explosive)
        self.assertIsNotNone(blocked_explosive)
        assert open_explosive is not None
        assert blocked_explosive is not None

        open_explosive.arming_ticks = 1
        open_explosive.fuse_ticks = 5
        open_explosive.trigger_radius = 40
        blocked_explosive.arming_ticks = 1
        blocked_explosive.fuse_ticks = 5
        blocked_explosive.trigger_radius = 40

        open_explosives = [open_explosive]
        blocked_explosives = [blocked_explosive]
        open_report = update_player_explosives(
            open_explosives,
            [enemy_open],
            player,
            level=open_level,
        )
        blocked_report = update_player_explosives(
            blocked_explosives,
            [enemy_blocked],
            player,
            level=blocked_level,
        )

        self.assertEqual(open_report.detonations, 1)
        self.assertEqual(len(open_explosives), 0)
        self.assertEqual(blocked_report.detonations, 0)
        self.assertEqual(len(blocked_explosives), 1)

    def test_player_mine_splash_respects_crate_cover_in_tight_corridor(self) -> None:
        corridor_walls = {(1, tile_y) for tile_y in range(1, 8)}
        corridor_walls.update({(3, tile_y) for tile_y in range(1, 8)})
        level = _build_level(width=6, height=10, walls=corridor_walls)
        open_player = PlayerState(x=0.0, y=0.0)
        cover_player = PlayerState(x=0.0, y=0.0)
        enemy_open = EnemyState(
            enemy_id=0,
            type_index=0,
            x=34.0,
            y=38.0,
            health=18.0,
            max_health=18.0,
        )
        enemy_cover = EnemyState(
            enemy_id=0,
            type_index=0,
            x=34.0,
            y=38.0,
            health=18.0,
            max_health=18.0,
        )
        cover_crate = CrateState(
            crate_id=0,
            type1=0,
            type2=0,
            x=42.0,
            y=46.0,
            health=12.0,
            max_health=12.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=34,
            weapon_slot=11,
            impact_x=54,
            impact_y=98,
        )

        open_mine = deploy_player_explosive_from_shot(shot)
        cover_mine = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(open_mine)
        self.assertIsNotNone(cover_mine)
        assert open_mine is not None
        assert cover_mine is not None
        open_mine.fuse_ticks = 1
        open_mine.arming_ticks = 0
        open_mine.trigger_radius = 0
        cover_mine.fuse_ticks = 1
        cover_mine.arming_ticks = 0
        cover_mine.trigger_radius = 0

        open_report = update_player_explosives(
            [open_mine],
            [enemy_open],
            open_player,
            level=level,
        )
        cover_report = update_player_explosives(
            [cover_mine],
            [enemy_cover],
            cover_player,
            level=level,
            crates=[cover_crate],
        )

        self.assertEqual(open_report.enemies_hit, 1)
        self.assertEqual(cover_report.enemies_hit, 0)
        self.assertLess(enemy_open.health, enemy_cover.health)
        self.assertEqual(enemy_cover.health, enemy_cover.max_health)
        self.assertFalse(cover_crate.alive)

    def test_player_mine_proximity_trigger_respects_crate_obstruction(self) -> None:
        level = _build_level(height=12)
        player = PlayerState(x=0.0, y=0.0)
        enemy_open = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=84.0,
            health=18.0,
            max_health=18.0,
        )
        enemy_blocked = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=84.0,
            health=18.0,
            max_health=18.0,
        )
        blocking_crate = CrateState(
            crate_id=0,
            type1=1,
            type2=0,
            x=47.0,
            y=74.0,
            health=12.0,
            max_health=12.0,
        )
        shot = ShotEvent(
            origin_x=54.0,
            origin_y=64.0,
            angle=0,
            max_distance=34,
            weapon_slot=11,
            impact_x=54,
            impact_y=98,
        )

        open_explosive = deploy_player_explosive_from_shot(shot)
        blocked_explosive = deploy_player_explosive_from_shot(shot)
        self.assertIsNotNone(open_explosive)
        self.assertIsNotNone(blocked_explosive)
        assert open_explosive is not None
        assert blocked_explosive is not None

        open_explosive.arming_ticks = 1
        open_explosive.fuse_ticks = 5
        open_explosive.trigger_radius = 40
        blocked_explosive.arming_ticks = 1
        blocked_explosive.fuse_ticks = 5
        blocked_explosive.trigger_radius = 40

        open_explosives = [open_explosive]
        blocked_explosives = [blocked_explosive]
        open_report = update_player_explosives(
            open_explosives,
            [enemy_open],
            player,
            level=level,
        )
        blocked_report = update_player_explosives(
            blocked_explosives,
            [enemy_blocked],
            player,
            level=level,
            crates=[blocking_crate],
        )

        self.assertEqual(open_report.detonations, 1)
        self.assertEqual(len(open_explosives), 0)
        self.assertEqual(blocked_report.detonations, 0)
        self.assertEqual(len(blocked_explosives), 1)

    def test_enemy_behavior_corner_graze_line_of_sight_is_blocked(self) -> None:
        level = _build_level(width=10, height=10, walls={(3, 3)})
        player = PlayerState(x=54.0, y=76.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=6.0,
            y=6.0,
            health=18.0,
            max_health=18.0,
            angle=34,
            target_angle=34,
            load_count=10,
        )

        report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertEqual(report.hits_on_player, 0)
        self.assertEqual(player.health, 100.0)
        self.assertFalse(enemy.sees_player)

    def test_enemy_behavior_does_not_shoot_through_walls(self) -> None:
        level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=40.0, y=40.0)
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=40.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
            load_count=10,
        )

        report = update_enemy_behavior(level, [enemy], player)

        self.assertEqual(report.shots_fired, 0)
        self.assertEqual(report.hits_on_player, 0)
        self.assertEqual(player.health, 100.0)
        self.assertFalse(enemy.sees_player)


if __name__ == "__main__":
    unittest.main()

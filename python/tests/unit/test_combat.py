from __future__ import annotations

import sys
from pathlib import Path
import unittest


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
from ultimatetk.systems.combat import (
    CrateState,
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

    def test_grenade_projectile_near_miss_applies_splash_damage(self) -> None:
        level = _build_level(height=12)
        blocked_level = _build_level(height=12, walls={(2, 3)})
        player = PlayerState(x=36.0, y=64.0)
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

    def test_grenade_projectile_near_miss_is_fully_blocked_by_wall_fan(self) -> None:
        level = _build_level(height=12)
        blocked_level = _build_level(height=12, walls={(2, 3), (2, 4)})
        player = PlayerState(x=36.0, y=64.0)
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

        self.assertEqual(mine.kind, "mine")
        self.assertEqual(mine.fuse_ticks, 2000)
        self.assertEqual(mine.arming_ticks, 26)
        self.assertEqual(mine.radius, 20)

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
            x=48.0,
            y=84.0,
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

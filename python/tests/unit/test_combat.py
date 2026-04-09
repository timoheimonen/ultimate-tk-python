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
    resolve_enemy_attack_against_player,
    resolve_shot_against_enemies,
    spawn_crates_for_level,
    spawn_enemies_for_level,
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

        self.assertEqual(attack.hit_count, 1)
        self.assertGreater(attack.total_damage, 0.0)
        self.assertLess(attack.total_damage, 20.0)
        self.assertLess(player.health, 100.0)

    def test_grenade_projectile_near_miss_applies_splash_damage(self) -> None:
        level = _build_level(height=12)
        blocked_level = _build_level(height=12, walls={(2, 3)})
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

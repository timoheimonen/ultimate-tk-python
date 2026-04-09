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
    GeneralLevelInfo,
    LevelData,
)
from ultimatetk.systems.combat import (
    EnemyState,
    advance_enemy_effects,
    alive_enemy_count,
    resolve_shot_against_enemies,
    spawn_enemies_for_level,
    update_enemy_behavior,
)
from ultimatetk.systems.player_control import PlayerState, ShotEvent


def _build_level(
    *,
    width: int = 10,
    height: int = 10,
    walls: set[tuple[int, int]] | None = None,
    start: tuple[int, int] = (2, 2),
    enemies: tuple[int, ...] | None = None,
) -> LevelData:
    wall_tiles = walls or set()
    blocks = []
    for y in range(height):
        for x in range(width):
            block_type = 1 if (x, y) in wall_tiles else 0
            blocks.append(Block(type=block_type, num=0, shadow=0))

    crate_counts = CrateCounts(
        weapon_crates=tuple(0 for _ in range(DIFF_WEAPONS)),
        bullet_crates=tuple(0 for _ in range(DIFF_BULLETS)),
        energy_crates=0,
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
        normal_crate_info=(),
        deathmatch_crate_info=(),
    )


class CombatSystemTests(unittest.TestCase):
    def test_spawn_uses_level_enemy_counts(self) -> None:
        level = _build_level(enemies=(1, 0, 0, 0, 0, 0, 0, 0))

        spawned = spawn_enemies_for_level(level, player_x=40.0, player_y=40.0)

        self.assertEqual(len(spawned), 1)
        self.assertEqual(spawned[0].type_index, 0)
        self.assertEqual((int(spawned[0].x), int(spawned[0].y)), (40, 80))

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

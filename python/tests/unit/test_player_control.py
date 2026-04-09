from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.events import InputAction
from ultimatetk.formats.lev import (
    DIFF_BULLETS,
    DIFF_ENEMIES,
    DIFF_WEAPONS,
    Block,
    CrateCounts,
    GeneralLevelInfo,
    LevelData,
)
from ultimatetk.systems.player_control import (
    aim_point_from_player,
    apply_player_controls,
    cycle_weapon_slot,
    follow_player_camera,
    select_weapon_slot_if_owned,
    spawn_player_from_level,
)


def _build_level(
    *,
    width: int = 8,
    height: int = 8,
    walls: set[tuple[int, int]] | None = None,
    start: tuple[int, int] = (2, 2),
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
    return LevelData(
        version=5,
        level_x_size=width,
        level_y_size=height,
        blocks=tuple(blocks),
        player_start_x=(start[0], start[0]),
        player_start_y=(start[1], start[1]),
        spots=(),
        steams=(),
        general_info=GeneralLevelInfo(comment="", time_limit=0, enemies=tuple(0 for _ in range(DIFF_ENEMIES))),
        normal_crate_counts=crate_counts,
        deathmatch_crate_counts=crate_counts,
        normal_crate_info=(),
        deathmatch_crate_info=(),
    )


class PlayerControlTests(unittest.TestCase):
    def test_spawn_player_from_level_uses_tile_coordinates(self) -> None:
        level = _build_level(start=(3, 4))
        player = spawn_player_from_level(level)

        self.assertEqual(player.x, 60.0)
        self.assertEqual(player.y, 80.0)

    def test_forward_motion_uses_legacy_speed(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)

        apply_player_controls(player, level, {InputAction.MOVE_FORWARD})

        self.assertAlmostEqual(player.x, 40.0)
        self.assertAlmostEqual(player.y, 42.0)

    def test_rotation_changes_by_nine_degrees(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)

        apply_player_controls(player, level, {InputAction.TURN_LEFT})
        self.assertEqual(player.angle, 9)

        apply_player_controls(player, level, {InputAction.TURN_RIGHT})
        self.assertEqual(player.angle, 0)

    def test_strafe_modifier_moves_without_rotation(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)

        apply_player_controls(
            player,
            level,
            {InputAction.STRAFE_MODIFIER, InputAction.TURN_LEFT},
        )

        self.assertEqual(player.angle, 0)
        self.assertAlmostEqual(player.x, 41.8)
        self.assertAlmostEqual(player.y, 40.0)

    def test_wall_collision_blocks_forward_motion(self) -> None:
        level = _build_level(walls={(2, 3)})
        player = spawn_player_from_level(level)

        apply_player_controls(player, level, {InputAction.MOVE_FORWARD})

        self.assertAlmostEqual(player.x, 40.0)
        self.assertAlmostEqual(player.y, 40.0)

    def test_weapon_cycle_skips_unowned_slots(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)
        player.grant_weapon(2)
        player.grant_weapon(4)

        cycle_weapon_slot(player)
        self.assertEqual(player.current_weapon, 2)
        cycle_weapon_slot(player)
        self.assertEqual(player.current_weapon, 4)
        cycle_weapon_slot(player)
        self.assertEqual(player.current_weapon, 0)

    def test_weapon_select_only_accepts_owned_slots(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)

        select_weapon_slot_if_owned(player, 5)
        self.assertEqual(player.current_weapon, 0)

        player.grant_weapon(5)
        select_weapon_slot_if_owned(player, 5)
        self.assertEqual(player.current_weapon, 5)

        select_weapon_slot_if_owned(player, 20)
        self.assertEqual(player.current_weapon, 5)

    def test_follow_camera_clamps_for_small_levels(self) -> None:
        level = _build_level(width=8, height=8)
        player = spawn_player_from_level(level)

        camera_x, camera_y = follow_player_camera(
            camera_x=50,
            camera_y=70,
            player=player,
            max_camera_x=0,
            max_camera_y=0,
        )
        self.assertEqual(camera_x, 0)
        self.assertEqual(camera_y, 0)

    def test_follow_camera_moves_toward_look_direction(self) -> None:
        level = _build_level(width=40, height=30, start=(12, 8))
        player = spawn_player_from_level(level)
        player.angle = 90

        start_camera_x = int(player.center_x) - 160
        start_camera_y = int(player.center_y) - 100
        next_camera_x, _ = follow_player_camera(
            camera_x=start_camera_x,
            camera_y=start_camera_y,
            player=player,
            max_camera_x=(level.level_x_size * 20) - 320,
            max_camera_y=(level.level_y_size * 20) - 200,
        )
        self.assertGreater(next_camera_x, start_camera_x)

    def test_aim_point_tracks_player_angle(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)

        player.angle = 0
        self.assertEqual(aim_point_from_player(player), (54, 64))

        player.angle = 90
        self.assertEqual(aim_point_from_player(player), (64, 54))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
from pathlib import Path
import unittest

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    np = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if np is not None:
    from ultimatetk.ai.observation import CHANNEL_ENEMY, CHANNEL_PROJECTILE, RAY_SECTOR_COUNT, extract_observation
    from ultimatetk.core.state import RuntimeState
    from ultimatetk.formats.lev import Block, CrateCounts, GeneralLevelInfo, LevelData
    from ultimatetk.rendering.constants import FLOOR_BLOCK_TYPE, WALL_BLOCK_TYPE
    from ultimatetk.systems.combat import CrateState, EnemyProjectile, EnemyState
    from ultimatetk.systems.gameplay_scene import GameplayStateView
    from ultimatetk.systems.player_control import PlayerState


def _build_level(*, wall_tile: tuple[int, int] | None = None) -> LevelData:
    width = 5
    height = 5
    blocks: list[Block] = []
    for y in range(height):
        for x in range(width):
            block_type = FLOOR_BLOCK_TYPE
            if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                block_type = WALL_BLOCK_TYPE
            if wall_tile is not None and (x, y) == wall_tile:
                block_type = WALL_BLOCK_TYPE
            blocks.append(Block(type=block_type, num=0, shadow=0))

    return LevelData(
        version=5,
        level_x_size=width,
        level_y_size=height,
        blocks=tuple(blocks),
        player_start_x=(2, 2),
        player_start_y=(1, 1),
        spots=(),
        steams=(),
        general_info=GeneralLevelInfo(comment="", time_limit=0, enemies=(0, 0, 0, 0, 0, 0, 0, 0)),
        normal_crate_counts=CrateCounts(weapon_crates=(), bullet_crates=(), energy_crates=0),
        deathmatch_crate_counts=CrateCounts(weapon_crates=(), bullet_crates=(), energy_crates=0),
        normal_crate_info=(),
        deathmatch_crate_info=(),
    )


@unittest.skipIf(np is None, "numpy optional dependency is not installed")
class GymObservationTests(unittest.TestCase):
    def test_occluded_enemy_does_not_pop_visible_enemy_channel(self) -> None:
        level = _build_level(wall_tile=(2, 2))
        player = PlayerState(x=40.0, y=20.0, angle=0)
        enemy = EnemyState(
            enemy_id=1,
            type_index=0,
            x=40.0,
            y=60.0,
            health=10.0,
            max_health=10.0,
        )

        view = GameplayStateView(
            level=level,
            player=player,
            enemies=(enemy,),
            crates=(),
            enemy_projectiles=(),
            player_explosives=(),
            shop_active=False,
        )
        runtime = RuntimeState(enemies_total=1, enemies_alive=1)
        observation = extract_observation(view, runtime)

        rays = observation["rays"]
        self.assertEqual(rays.shape, (RAY_SECTOR_COUNT, 8))
        self.assertAlmostEqual(float(rays[0, CHANNEL_ENEMY]), 1.0, places=6)

    def test_visible_projectile_updates_projectile_channel_and_state(self) -> None:
        level = _build_level()
        player = PlayerState(x=40.0, y=20.0, angle=0)
        projectile = EnemyProjectile(
            owner_enemy_id=1,
            weapon_slot=1,
            x=54.0,
            y=42.0,
            vx=0.0,
            vy=1.0,
            speed=5.0,
            damage=1.0,
            remaining_ticks=20,
            radius=2,
        )
        crate = CrateState(
            crate_id=1,
            type1=1,
            type2=0,
            x=40.0,
            y=44.0,
            health=5.0,
            max_health=5.0,
        )

        view = GameplayStateView(
            level=level,
            player=player,
            enemies=(),
            crates=(crate,),
            enemy_projectiles=(projectile,),
            player_explosives=(),
            shop_active=False,
        )
        runtime = RuntimeState(
            player_current_ammo_capacity=100,
            player_current_ammo_units=10,
            crates_total=1,
            crates_alive=1,
        )
        observation = extract_observation(view, runtime)

        rays = observation["rays"]
        state = observation["state"]
        self.assertLess(float(np.min(rays[:, CHANNEL_PROJECTILE])), 1.0)
        self.assertLess(float(state[13]), 1.0)
        self.assertLess(float(state[14]), 1.0)


if __name__ == "__main__":
    unittest.main()

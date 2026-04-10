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
    from ultimatetk.ai.gym_env import UltimateTKEnv, gym_available
    from ultimatetk.systems.gameplay_scene import GameplayScene
else:
    def gym_available() -> bool:
        return False


def _noop_action() -> dict[str, np.ndarray | int]:
    return {
        "hold": np.zeros((8,), dtype=np.int8),
        "trigger": np.zeros((1,), dtype=np.int8),
        "weapon_select": 0,
    }


@unittest.skipUnless(np is not None and gym_available(), "gymnasium/numpy optional dependencies are not installed")
class GymEnvProgressionIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        if not (PROJECT_ROOT / "game_data" / "palette.tab").exists():
            self.skipTest("game_data assets not available")

    def test_level_complete_progresses_to_next_level(self) -> None:
        env = UltimateTKEnv(project_root=str(PROJECT_ROOT), enforce_asset_manifest=True)
        try:
            env.reset(seed=11)

            assert env._driver is not None
            scene = env._driver.scene_manager.current_scene
            if not isinstance(scene, GameplayScene):
                self.skipTest("gameplay scene did not initialize")

            has_next = scene._level_exists_for_session_index(env._driver.context, 1)  # type: ignore[attr-defined]
            if not has_next:
                self.skipTest("next level asset missing for progression test")

            scene._enemies.clear()  # type: ignore[attr-defined]

            _, _, terminated, truncated, _ = env.step(_noop_action())
            self.assertFalse(terminated)
            self.assertFalse(truncated)

            confirm = _noop_action()
            confirm["trigger"] = np.array([1], dtype=np.int8)
            env.step(confirm)

            env.step(_noop_action())
            self.assertEqual(env._driver.context.session.level_index, 1)
            self.assertEqual(env._driver.scene_manager.current_scene_name, "gameplay")
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()

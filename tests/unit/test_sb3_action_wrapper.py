from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    gym = None
    spaces = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


if gym is not None:
    from ultimatetk.ai.sb3_action_wrapper import ACTION_VECTOR_SIZE, SB3ActionWrapper


@unittest.skipUnless(gym is not None and spaces is not None, "gymnasium optional dependency is not installed")
class SB3ActionWrapperTests(unittest.TestCase):
    def test_action_space_matches_expected_multidiscrete_layout(self) -> None:
        env = _DummyGymEnv()
        wrapped = SB3ActionWrapper(env)
        self.assertEqual(int(wrapped.action_space.nvec.shape[0]), ACTION_VECTOR_SIZE)
        self.assertEqual(tuple(int(v) for v in wrapped.action_space.nvec), (2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 13))
        wrapped.close()

    def test_step_translates_vector_to_env_dict_action(self) -> None:
        env = _DummyGymEnv()
        wrapped = SB3ActionWrapper(env)
        wrapped.reset(seed=7)

        action = np.asarray((1, 0, 1, 0, 0, 1, 1, 0, 0, 1, 12), dtype=np.int64)
        wrapped.step(action)

        assert env.last_action is not None
        self.assertEqual(tuple(int(v) for v in env.last_action["hold"]), (1, 0, 1, 0, 0, 1, 1, 0))
        self.assertEqual(tuple(int(v) for v in env.last_action["trigger"]), (0, 1))
        self.assertEqual(int(env.last_action["weapon_select"]), 12)
        wrapped.close()

    def test_invalid_action_vector_size_raises(self) -> None:
        env = _DummyGymEnv()
        wrapped = SB3ActionWrapper(env)
        wrapped.reset(seed=5)
        with self.assertRaises(ValueError):
            wrapped.step(np.asarray((1, 0, 1), dtype=np.int64))
        wrapped.close()


if gym is not None and spaces is not None:

    class _DummyGymEnv(gym.Env):  # type: ignore[misc]
        metadata = {"render_modes": []}

        def __init__(self) -> None:
            super().__init__()
            self.observation_space = spaces.Dict(
                {
                    "rays": spaces.Box(low=0.0, high=1.0, shape=(32, 8), dtype=np.float32),
                    "state": spaces.Box(low=0.0, high=1.0, shape=(16,), dtype=np.float32),
                },
            )
            self.action_space = spaces.Dict(
                {
                    "hold": spaces.MultiBinary(8),
                    "trigger": spaces.MultiBinary(2),
                    "weapon_select": spaces.Discrete(13),
                },
            )
            self.last_action: dict[str, np.ndarray | int] | None = None

        def reset(self, *, seed: int | None = None, options: dict[str, object] | None = None):
            del seed
            del options
            observation = {
                "rays": np.ones((32, 8), dtype=np.float32),
                "state": np.zeros((16,), dtype=np.float32),
            }
            return observation, {}

        def step(self, action):
            self.last_action = action
            observation = {
                "rays": np.ones((32, 8), dtype=np.float32),
                "state": np.zeros((16,), dtype=np.float32),
            }
            return observation, 0.0, False, False, {}

else:

    class _DummyGymEnv:  # pragma: no cover - dependency skip path
        pass


if __name__ == "__main__":
    unittest.main()

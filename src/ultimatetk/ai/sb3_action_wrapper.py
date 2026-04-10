from __future__ import annotations

from typing import Any

import numpy as np


try:
    import gymnasium as gym
    from gymnasium import spaces
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    gym = None
    spaces = None


ACTION_VECTOR_SIZE = 11
_ACTION_NVECS = np.asarray((2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 13), dtype=np.int64)


def build_sb3_action_space() -> Any:
    if spaces is None:
        raise RuntimeError("gymnasium is required for SB3 action wrapper")
    return spaces.MultiDiscrete(_ACTION_NVECS.copy())


if gym is None:

    class SB3ActionWrapper:  # pragma: no cover - import shim for optional deps
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            del args
            del kwargs
            raise RuntimeError("gymnasium is required for SB3 action wrapper")

else:

    class SB3ActionWrapper(gym.ActionWrapper):
        """Expose a PPO-friendly MultiDiscrete action space over UltimateTKEnv."""

        def __init__(self, env: gym.Env) -> None:
            super().__init__(env)
            self.action_space = build_sb3_action_space()

        def action(self, action: Any) -> dict[str, Any]:
            vector = np.asarray(action, dtype=np.int64).reshape(-1)
            if vector.size != ACTION_VECTOR_SIZE:
                raise ValueError(
                    f"expected action vector of size {ACTION_VECTOR_SIZE}, got {vector.size}",
                )

            hold = (vector[0:8] != 0).astype(np.int8, copy=False)
            trigger = (vector[8:10] != 0).astype(np.int8, copy=False)
            weapon_select = int(np.clip(vector[10], 0, 12))

            return {
                "hold": hold,
                "trigger": trigger,
                "weapon_select": weapon_select,
            }

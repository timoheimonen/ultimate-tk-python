from __future__ import annotations

import random
from typing import Any

from ultimatetk.core.state import AppMode


try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-optional environments
    np = None

try:
    import gymnasium as gym
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-optional environments
    gym = None

if gym is not None and np is not None:
    from ultimatetk.ai.action_codec import ActionCodec, build_action_space
    from ultimatetk.ai.observation import blank_observation, build_observation_space, extract_observation
    from ultimatetk.ai.reward import RewardConfig, RewardTracker
    from ultimatetk.ai.runtime_driver import TrainingRuntimeDriver


def gym_available() -> bool:
    return gym is not None and np is not None


if gym is None or np is None:

    class UltimateTKEnv:  # pragma: no cover - small runtime error shim
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            del args
            del kwargs
            raise RuntimeError(
                "gymnasium/numpy are not installed. Install optional dependencies with: "
                "python3 -m pip install -e '.[ai]'",
            )

else:

    class UltimateTKEnv(gym.Env):
        metadata = {"render_modes": []}

        def __init__(
            self,
            *,
            max_episode_steps: int = 6000,
            target_tick_rate: int = 40,
            enforce_asset_manifest: bool = True,
            project_root: str | None = None,
            render_enabled: bool = False,
            weapon_mode: str = "normal_mode",
            reward_config: RewardConfig | None = None,
            randomize_level_on_reset: bool = False,
            level_index_pool: tuple[int, ...] | None = None,
            frame_skip: int = 4,
        ) -> None:
            super().__init__()
            self._max_episode_steps = max(1, int(max_episode_steps))
            self._target_tick_rate = max(1, int(target_tick_rate))
            self._enforce_asset_manifest = bool(enforce_asset_manifest)
            self._project_root = project_root
            self._render_enabled = bool(render_enabled)
            self._weapon_mode = str(weapon_mode)
            self._frame_skip = max(1, int(frame_skip))
            self._randomize_level_on_reset = bool(randomize_level_on_reset)
            if level_index_pool is None:
                self._level_index_pool = (0,)
            else:
                cleaned_pool = tuple(sorted({max(0, int(index)) for index in level_index_pool}))
                self._level_index_pool = cleaned_pool or (0,)

            self._driver: TrainingRuntimeDriver | None = None
            self._action_codec = ActionCodec()
            self._reward_tracker = RewardTracker(config=reward_config)
            self._episode_steps = 0
            self._last_observation: dict[str, np.ndarray] | None = None

            self.action_space = build_action_space()
            self.observation_space = build_observation_space()

        def reset(
            self,
            *,
            seed: int | None = None,
            options: dict[str, Any] | None = None,
        ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
            super().reset(seed=seed)

            if seed is not None:
                random.seed(seed)
                np.random.seed(seed % (2**32))

            options_dict = options or {}
            if "level_index" in options_dict:
                level_index = max(0, int(options_dict.get("level_index", 0)))
            elif self._randomize_level_on_reset and self._level_index_pool:
                level_index = int(random.choice(self._level_index_pool))
            else:
                level_index = 0

            if self._driver is not None:
                self._driver.close()

            self._driver = TrainingRuntimeDriver.create(
                level_index=level_index,
                target_tick_rate=self._target_tick_rate,
                enforce_asset_manifest=self._enforce_asset_manifest,
                project_root=self._project_root,
                render_enabled=self._render_enabled,
                weapon_mode=self._weapon_mode,
            )

            runtime = self._driver.context.runtime
            view = self._driver.gameplay_view()
            if view is None:
                raise RuntimeError("failed to initialize gameplay scene for gym environment")

            self._action_codec.reset()
            self._reward_tracker.reset(runtime)
            self._episode_steps = 0

            observation = extract_observation(view, runtime)
            self._last_observation = observation

            info: dict[str, Any] = {
                "level_index": int(self._driver.context.session.level_index),
                "game_completed": False,
                "terminal_reason": "",
            }
            return observation, info

        def step(
            self,
            action: dict[str, Any],
        ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
            if self._driver is None:
                raise RuntimeError("reset() must be called before step()")

            events = self._action_codec.decode(action)
            total_reward = 0.0
            terminal_info: dict[str, Any] = {}
            accumulated_breakdown: dict[str, float] = {}

            for _ in range(self._frame_skip):
                self._driver.step(events)
                self._episode_steps += 1

                runtime = self._driver.context.runtime
                view = self._driver.gameplay_view()
                if view is None:
                    observation = self._last_observation or blank_observation(runtime)
                else:
                    observation = extract_observation(view, runtime)
                self._last_observation = observation

                reward_step = self._reward_tracker.step(runtime, observation)
                total_reward += float(reward_step.value)

                if not accumulated_breakdown:
                    accumulated_breakdown = dict(reward_step.breakdown)
                else:
                    for key, value in reward_step.breakdown.items():
                        accumulated_breakdown[key] = accumulated_breakdown.get(key, 0.0) + value

                terminated = False
                truncated = False
                game_completed = False
                terminal_reason = ""

                if runtime.player_dead:
                    terminated = True
                    terminal_reason = "death"
                elif runtime.mode == AppMode.RUN_COMPLETE or runtime.progression_event == "run_complete":
                    terminated = True
                    game_completed = True
                    terminal_reason = "game_completed"
                elif self._episode_steps >= self._max_episode_steps:
                    truncated = True
                    terminal_reason = "time_limit"

                terminal_info = {
                    "level_index": int(self._driver.context.session.level_index),
                    "game_completed": game_completed,
                    "terminal_reason": terminal_reason,
                    "inactivity_ticks": reward_step.inactivity_ticks,
                    "reward_breakdown": accumulated_breakdown,
                }

                if terminated or truncated:
                    return observation, total_reward, terminated, truncated, terminal_info

            return observation, total_reward, False, False, terminal_info

        def close(self) -> None:
            if self._driver is not None:
                self._driver.close()
                self._driver = None

        def set_penalty_scale(self, scale: float) -> None:
            self._reward_tracker.set_penalty_scale(scale)


def make_env(**kwargs: Any) -> UltimateTKEnv:
    return UltimateTKEnv(**kwargs)

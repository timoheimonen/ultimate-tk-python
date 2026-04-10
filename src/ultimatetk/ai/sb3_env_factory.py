from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ultimatetk.ai.gym_env import UltimateTKEnv
from ultimatetk.ai.sb3_action_wrapper import SB3ActionWrapper


def build_sb3_env_factory(
    *,
    project_root: str | Path,
    max_episode_steps: int,
    target_tick_rate: int,
    enforce_asset_manifest: bool,
    render_enabled: bool = False,
) -> Callable[[], Any]:
    resolved_root = str(Path(project_root).expanduser().resolve())

    def _make_env() -> Any:
        env = UltimateTKEnv(
            project_root=resolved_root,
            max_episode_steps=max_episode_steps,
            target_tick_rate=target_tick_rate,
            enforce_asset_manifest=enforce_asset_manifest,
            render_enabled=render_enabled,
        )
        return SB3ActionWrapper(env)

    return _make_env

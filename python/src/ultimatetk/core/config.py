from __future__ import annotations

from dataclasses import dataclass

from ultimatetk.core.constants import (
    DEFAULT_MAX_FRAME_TIME_SECONDS,
    DEFAULT_MAX_UPDATES_PER_FRAME,
    DEFAULT_TARGET_TICK_RATE,
)


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    target_tick_rate: int = DEFAULT_TARGET_TICK_RATE
    max_frame_time_seconds: float = DEFAULT_MAX_FRAME_TIME_SECONDS
    max_updates_per_frame: int = DEFAULT_MAX_UPDATES_PER_FRAME
    max_seconds: float | None = None
    autostart_gameplay: bool = False
    status_print_interval: int = 0
    platform: str = "headless"
    terminal_hold_frames: int = 2
    input_script: str | None = None

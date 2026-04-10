from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter


@dataclass(slots=True)
class FixedStepClock:
    target_tick_rate: int
    max_frame_time_seconds: float
    fixed_dt_seconds: float = field(init=False)
    total_seconds: float = 0.0
    accumulator_seconds: float = 0.0
    _last_time_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.target_tick_rate <= 0:
            raise ValueError("target_tick_rate must be positive")
        if self.max_frame_time_seconds <= 0:
            raise ValueError("max_frame_time_seconds must be positive")
        self.fixed_dt_seconds = 1.0 / float(self.target_tick_rate)

    def start(self, now_seconds: float | None = None) -> None:
        self._last_time_seconds = perf_counter() if now_seconds is None else now_seconds

    def tick(self, now_seconds: float | None = None) -> float:
        now = perf_counter() if now_seconds is None else now_seconds
        if self._last_time_seconds is None:
            self.start(now)
            return 0.0

        frame_delta = now - self._last_time_seconds
        self._last_time_seconds = now

        if frame_delta < 0:
            frame_delta = 0.0
        if frame_delta > self.max_frame_time_seconds:
            frame_delta = self.max_frame_time_seconds

        self.total_seconds += frame_delta
        self.accumulator_seconds += frame_delta
        return frame_delta

    def has_pending_update(self) -> bool:
        return self.accumulator_seconds >= self.fixed_dt_seconds

    def pop_update(self) -> bool:
        if not self.has_pending_update():
            return False
        self.accumulator_seconds -= self.fixed_dt_seconds
        return True

    def drop_pending_time(self) -> None:
        self.accumulator_seconds = 0.0

    @property
    def interpolation_alpha(self) -> float:
        return self.accumulator_seconds / self.fixed_dt_seconds

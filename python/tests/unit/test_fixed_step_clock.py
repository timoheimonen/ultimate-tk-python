from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.fixed_step import FixedStepClock


class FixedStepClockTests(unittest.TestCase):
    def test_single_update_after_one_tick_interval(self) -> None:
        clock = FixedStepClock(target_tick_rate=40, max_frame_time_seconds=0.25)
        clock.start(now_seconds=1.0)
        clock.tick(now_seconds=1.0 + clock.fixed_dt_seconds + 1e-9)

        self.assertTrue(clock.pop_update())
        self.assertFalse(clock.pop_update())
        self.assertAlmostEqual(clock.interpolation_alpha, 0.0, places=6)

    def test_long_frame_is_clamped(self) -> None:
        clock = FixedStepClock(target_tick_rate=40, max_frame_time_seconds=0.25)
        clock.start(now_seconds=0.0)
        delta = clock.tick(now_seconds=1.5)

        self.assertAlmostEqual(delta, 0.25, places=6)
        self.assertAlmostEqual(clock.total_seconds, 0.25, places=6)


if __name__ == "__main__":
    unittest.main()

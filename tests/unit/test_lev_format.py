from __future__ import annotations

import struct
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.formats.lev import parse_lev


def _pack_i32(*values: int) -> bytes:
    return struct.pack(f"<{len(values)}i", *values)


class LevFormatTests(unittest.TestCase):
    def test_parse_version5_level(self) -> None:
        parts: list[bytes] = []
        parts.append(_pack_i32(5, 2, 1))
        parts.append(_pack_i32(0, 1, 2))
        parts.append(_pack_i32(1, 3, 4))
        parts.append(_pack_i32(10, 20, 30, 40))

        parts.append(_pack_i32(1))
        parts.append(_pack_i32(100, 200, 3))

        parts.append(_pack_i32(1))
        parts.append(_pack_i32(11, 22, 33, 44))

        comment = b"hello level\x00".ljust(20, b"\x00")
        parts.append(comment)
        parts.append(_pack_i32(120))
        parts.append(_pack_i32(1, 2, 3, 4, 5, 6, 7, 8))

        parts.append(_pack_i32(*tuple(range(100, 111))))
        parts.append(_pack_i32(*tuple(range(200, 209))))
        parts.append(_pack_i32(300))

        parts.append(_pack_i32(*tuple(range(400, 411))))
        parts.append(_pack_i32(*tuple(range(500, 509))))
        parts.append(_pack_i32(600))

        parts.append(_pack_i32(1))
        parts.append(_pack_i32(1, 2, 3, 4))
        parts.append(_pack_i32(2))
        parts.append(_pack_i32(5, 6, 7, 8))
        parts.append(_pack_i32(9, 10, 11, 12))

        level = parse_lev(b"".join(parts))

        self.assertEqual(level.version, 5)
        self.assertEqual(level.level_x_size, 2)
        self.assertEqual(level.level_y_size, 1)
        self.assertEqual(len(level.blocks), 2)
        self.assertEqual(level.player_start_x, (10, 30))
        self.assertEqual(level.player_start_y, (20, 40))
        self.assertEqual(level.general_info.comment, "hello level")
        self.assertEqual(level.general_info.enemies, (1, 2, 3, 4, 5, 6, 7, 8))
        self.assertEqual(level.normal_crate_counts.energy_crates, 300)
        self.assertEqual(level.deathmatch_crate_counts.energy_crates, 600)
        self.assertEqual(len(level.normal_crate_info), 1)
        self.assertEqual(len(level.deathmatch_crate_info), 2)

    def test_parse_version3_enemy_padding(self) -> None:
        parts: list[bytes] = []
        parts.append(_pack_i32(3, 1, 1))
        parts.append(_pack_i32(0, 0, 0))
        parts.append(_pack_i32(1, 2, 3, 4))
        parts.append(_pack_i32(0))
        parts.append(_pack_i32(0))
        parts.append(b"legacy-v3\x00".ljust(20, b"\x00"))
        parts.append(_pack_i32(90))
        parts.append(_pack_i32(9, 8, 7, 6, 5, 4, 3))
        parts.append(_pack_i32(*tuple(range(11))))
        parts.append(_pack_i32(*tuple(range(9))))
        parts.append(_pack_i32(1))
        parts.append(_pack_i32(*tuple(range(11))))
        parts.append(_pack_i32(*tuple(range(9))))
        parts.append(_pack_i32(2))

        level = parse_lev(b"".join(parts))

        self.assertEqual(level.version, 3)
        self.assertEqual(len(level.general_info.enemies), 8)
        self.assertEqual(level.general_info.enemies[-1], 0)
        self.assertEqual(level.normal_crate_info, ())
        self.assertEqual(level.deathmatch_crate_info, ())


if __name__ == "__main__":
    unittest.main()

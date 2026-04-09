from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.rendering.framebuffer import IndexedFrameBuffer
from ultimatetk.rendering.software import build_dark_floor_sheet


class IndexedFrameBufferTests(unittest.TestCase):
    def test_blit_transparent_skips_zero_index(self) -> None:
        framebuffer = IndexedFrameBuffer(4, 4, fill=9)
        sprite = bytes(
            [
                0,
                2,
                3,
                0,
            ],
        )

        framebuffer.blit_transparent(sprite, 2, 2, 1, 1)

        self.assertEqual(framebuffer.pixels[1 * 4 + 1], 9)
        self.assertEqual(framebuffer.pixels[1 * 4 + 2], 2)
        self.assertEqual(framebuffer.pixels[2 * 4 + 1], 3)
        self.assertEqual(framebuffer.pixels[2 * 4 + 2], 9)

    def test_blit_translucent_uses_trans_table(self) -> None:
        framebuffer = IndexedFrameBuffer(3, 3, fill=5)
        sprite = bytes([7])
        trans_table = bytes(
            (src + dst) % 256
            for src in range(256)
            for dst in range(256)
        )

        framebuffer.blit_translucent(
            sprite,
            1,
            1,
            1,
            1,
            trans_table=trans_table,
        )

        self.assertEqual(framebuffer.pixels[1 * 3 + 1], 12)

    def test_apply_shadow_and_light_tables(self) -> None:
        framebuffer = IndexedFrameBuffer(2, 2, fill=10)
        mask = bytes([0, 3, 4, 0])

        shadow_table = bytes(
            (color + shade) % 256
            for color in range(256)
            for shade in range(16)
        )
        framebuffer.apply_shadow(
            mask,
            2,
            2,
            0,
            0,
            shadow_table=shadow_table,
        )

        self.assertEqual(framebuffer.pixels[0], 10)
        self.assertEqual(framebuffer.pixels[1], 13)
        self.assertEqual(framebuffer.pixels[2], 14)
        self.assertEqual(framebuffer.pixels[3], 10)

        light_table = bytes(
            power
            for _color in range(256)
            for power in range(16)
        )
        light_mask = bytes([1, 0, 15, 14])
        framebuffer.apply_light(
            light_mask,
            2,
            2,
            0,
            0,
            light_table=light_table,
            add=2,
        )

        self.assertEqual(framebuffer.pixels[0], 3)
        self.assertEqual(framebuffer.pixels[1], 13)
        self.assertEqual(framebuffer.pixels[2], 15)
        self.assertEqual(framebuffer.pixels[3], 15)

    def test_dark_floor_generation_uses_legacy_formula(self) -> None:
        floor_pixels = bytes([0, 1])
        palette = bytearray(256 * 3)
        palette[3:6] = bytes([10, 20, 30])

        dark = build_dark_floor_sheet(floor_pixels, bytes(palette))

        self.assertEqual(dark, bytes([223, 218]))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.formats.efp import EfpImage
from ultimatetk.formats.lev import Block, CrateCounts, GeneralLevelInfo, LevelData, Spot
from ultimatetk.formats.palette_tab import PaletteTables
from ultimatetk.rendering import RenderFlags, SoftwareRenderer, WorldSprite


def _make_level(*, blocks: tuple[Block, ...], width: int, height: int, spots: tuple[Spot, ...] = ()) -> LevelData:
    zeros_weapons = (0,) * 11
    zeros_bullets = (0,) * 9
    crates = CrateCounts(
        weapon_crates=zeros_weapons,
        bullet_crates=zeros_bullets,
        energy_crates=0,
    )
    return LevelData(
        version=5,
        level_x_size=width,
        level_y_size=height,
        blocks=blocks,
        player_start_x=(0, 0),
        player_start_y=(0, 0),
        spots=spots,
        steams=(),
        general_info=GeneralLevelInfo(comment="", time_limit=0, enemies=(0,) * 8),
        normal_crate_counts=crates,
        deathmatch_crate_counts=crates,
        normal_crate_info=(),
        deathmatch_crate_info=(),
    )


def _make_sheet(tile_values: dict[int, int]) -> bytes:
    sheet = bytearray(320 * 200)
    for tile_index, color in tile_values.items():
        src_x = (tile_index % 16) * 20
        src_y = (tile_index // 16) * 20
        for row in range(20):
            start = (src_y + row) * 320 + src_x
            sheet[start : start + 20] = bytes([color]) * 20
    return bytes(sheet)


def _make_shadow_sheet(shade_value: int = 0) -> bytes:
    sheet = bytearray(320 * 20)
    for row in range(20):
        start = row * 320
        sheet[start : start + 20] = bytes([shade_value]) * 20
    return bytes(sheet)


def _make_tables() -> PaletteTables:
    trans_table = bytes(
        (src + dst) % 256
        for src in range(256)
        for dst in range(256)
    )
    shadow_table = bytes(
        (color + shade) % 256
        for color in range(256)
        for shade in range(16)
    )
    light_table = bytes(
        power
        for _color in range(256)
        for power in range(16)
    )
    return PaletteTables(
        trans_table=trans_table,
        shadow_table=shadow_table,
        normal_light_table=light_table,
        red_light_table=light_table,
        yellow_light_table=light_table,
        explo_light_table=light_table,
    )


class SoftwareRendererTests(unittest.TestCase):
    def _make_renderer(self, level: LevelData) -> SoftwareRenderer:
        floor = EfpImage(
            width=320,
            height=200,
            pixels=_make_sheet({0: 10}),
            palette=bytes(256 * 3),
        )
        wall = EfpImage(
            width=320,
            height=200,
            pixels=_make_sheet({1: 30, 19: 99}),
            palette=bytes(256 * 3),
        )
        shadow = EfpImage(
            width=320,
            height=20,
            pixels=_make_shadow_sheet(2),
            palette=bytes(256 * 3),
        )

        return SoftwareRenderer.from_assets(
            level=level,
            floor_image=floor,
            wall_image=wall,
            shadow_image=shadow,
            palette_tables=_make_tables(),
        )

    def test_renders_floor_wall_and_outside_fallback(self) -> None:
        level = _make_level(
            width=2,
            height=1,
            blocks=(Block(type=0, num=0, shadow=0), Block(type=1, num=1, shadow=0)),
        )
        renderer = self._make_renderer(level)

        pixels = renderer.render(
            camera_x=0,
            camera_y=0,
            flags=RenderFlags(dark_mode=False, light_effects=False, shadows=False),
        )

        self.assertEqual(pixels[5 * 320 + 5], 10)
        self.assertEqual(pixels[5 * 320 + 25], 30)
        self.assertEqual(pixels[5 * 320 + 100], 99)

    def test_dark_mode_switches_floor_sheet(self) -> None:
        level = _make_level(
            width=1,
            height=1,
            blocks=(Block(type=0, num=0, shadow=0),),
        )
        renderer = self._make_renderer(level)

        pixels = renderer.render(
            camera_x=0,
            camera_y=0,
            flags=RenderFlags(dark_mode=True, light_effects=False, shadows=False),
        )

        self.assertEqual(pixels[5 * 320 + 5], 223)

    def test_spot_lights_use_light_table(self) -> None:
        level = _make_level(
            width=1,
            height=1,
            blocks=(Block(type=0, num=0, shadow=0),),
            spots=(Spot(x=10, y=10, size=0),),
        )
        renderer = self._make_renderer(level)

        pixels = renderer.render(
            camera_x=0,
            camera_y=0,
            flags=RenderFlags(dark_mode=False, light_effects=True, shadows=False),
            spot_phase_degrees=0,
        )

        self.assertEqual(pixels[10 * 320 + 10], 15)

    def test_translucent_sprite_uses_trans_table(self) -> None:
        level = _make_level(
            width=1,
            height=1,
            blocks=(Block(type=0, num=0, shadow=0),),
        )
        renderer = self._make_renderer(level)

        sprite = WorldSprite(
            world_x=5,
            world_y=5,
            width=1,
            height=1,
            pixels=bytes([7]),
            translucent=True,
        )
        pixels = renderer.render(
            camera_x=0,
            camera_y=0,
            flags=RenderFlags(dark_mode=False, light_effects=False, shadows=False),
            sprites=(sprite,),
        )

        self.assertEqual(pixels[5 * 320 + 5], 17)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import dataclass
import math
import zlib
from typing import Sequence

from ultimatetk.formats.efp import EfpImage
from ultimatetk.formats.lev import LevelData
from ultimatetk.formats.palette_tab import PaletteTables
from ultimatetk.rendering.constants import (
    FLOOR_BLOCK_TYPE,
    LIGHT_SIZES,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_SIZE,
    WALL_BLOCK_TYPE,
)
from ultimatetk.rendering.framebuffer import IndexedFrameBuffer


def _clamp(value: int, low: int, high: int) -> int:
    if value < low:
        return low
    if value > high:
        return high
    return value


def frame_digest(pixels: bytes) -> int:
    return zlib.adler32(pixels) & 0xFFFFFFFF


def build_dark_floor_sheet(floor_pixels: bytes, palette: bytes) -> bytes:
    if len(palette) != 256 * 3:
        raise ValueError("palette must be exactly 768 bytes")

    dark_sheet = bytearray(len(floor_pixels))
    for idx, color in enumerate(floor_pixels):
        base = color * 3
        lum = int(
            (palette[base + 0] * 0.2)
            + (palette[base + 1] * 0.5)
            + (palette[base + 2] * 0.3),
        )
        lum >>= 2
        mapped = (208 + 15) - lum
        if mapped < 0:
            mapped = 0
        elif mapped > 255:
            mapped = 255
        dark_sheet[idx] = mapped
    return bytes(dark_sheet)


def build_light_mask(size: int) -> bytes:
    if size <= 1:
        raise ValueError("light size must be greater than 1")

    half = size // 2
    scale = 16.0 / float(half)
    data = bytearray(size * size)
    for y in range(size):
        for x in range(size):
            dist = math.sqrt((y - half) * (y - half) + (x - half) * (x - half))
            power = int(16 - (dist * scale))
            if power < 0:
                power = 0
            elif power > 15:
                power = 15
            data[y * size + x] = power
    return bytes(data)


def build_light_masks() -> tuple[bytes, ...]:
    return tuple(build_light_mask(size) for size in LIGHT_SIZES)


def extract_horizontal_sprite_frame(
    image: EfpImage,
    *,
    frame_width: int,
    frame_height: int,
    frame_index: int,
) -> bytes:
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("frame dimensions must be positive")
    if frame_index < 0:
        raise ValueError("frame_index must be non-negative")
    if frame_height > image.height:
        raise ValueError("frame_height exceeds image height")

    src_x = frame_index * frame_width
    if src_x + frame_width > image.width:
        raise ValueError("frame index exceeds image width")

    out = bytearray(frame_width * frame_height)
    for row in range(frame_height):
        src_start = row * image.width + src_x
        dst_start = row * frame_width
        out[dst_start : dst_start + frame_width] = image.pixels[src_start : src_start + frame_width]
    return bytes(out)


def camera_from_player_start(level: LevelData, player_index: int = 0) -> tuple[int, int]:
    index = 0 if player_index <= 0 else 1
    world_x = level.player_start_x[index] * TILE_SIZE + (TILE_SIZE // 2)
    world_y = level.player_start_y[index] * TILE_SIZE + (TILE_SIZE // 2)
    return (
        world_x - (SCREEN_WIDTH // 2),
        world_y - (SCREEN_HEIGHT // 2),
    )


@dataclass(frozen=True, slots=True)
class RenderFlags:
    dark_mode: bool = True
    light_effects: bool = True
    shadows: bool = True


@dataclass(frozen=True, slots=True)
class WorldSprite:
    world_x: int
    world_y: int
    width: int
    height: int
    pixels: bytes
    anchor_x: int = 0
    anchor_y: int = 0
    translucent: bool = False


@dataclass(slots=True)
class SoftwareRenderer:
    level: LevelData
    floor_sheet: bytes
    wall_sheet: bytes
    dark_floor_sheet: bytes
    shadow_sheet: bytes
    palette_tables: PaletteTables
    palette_bytes: bytes
    light_masks: tuple[bytes, ...]
    framebuffer: IndexedFrameBuffer

    @classmethod
    def from_assets(
        cls,
        *,
        level: LevelData,
        floor_image: EfpImage,
        wall_image: EfpImage,
        shadow_image: EfpImage,
        palette_tables: PaletteTables,
    ) -> "SoftwareRenderer":
        if (floor_image.width, floor_image.height) != (SCREEN_WIDTH, SCREEN_HEIGHT):
            raise ValueError("floor sheet must be 320x200")
        if (wall_image.width, wall_image.height) != (SCREEN_WIDTH, SCREEN_HEIGHT):
            raise ValueError("wall sheet must be 320x200")
        if (shadow_image.width, shadow_image.height) != (SCREEN_WIDTH, TILE_SIZE):
            raise ValueError("shadow sheet must be 320x20")

        dark_floor_sheet = build_dark_floor_sheet(floor_image.pixels, wall_image.palette)
        return cls(
            level=level,
            floor_sheet=floor_image.pixels,
            wall_sheet=wall_image.pixels,
            dark_floor_sheet=dark_floor_sheet,
            shadow_sheet=shadow_image.pixels,
            palette_tables=palette_tables,
            palette_bytes=wall_image.palette,
            light_masks=build_light_masks(),
            framebuffer=IndexedFrameBuffer(SCREEN_WIDTH, SCREEN_HEIGHT),
        )

    @property
    def max_camera_x(self) -> int:
        return max(0, self.level.level_x_size * TILE_SIZE - SCREEN_WIDTH)

    @property
    def max_camera_y(self) -> int:
        return max(0, self.level.level_y_size * TILE_SIZE - SCREEN_HEIGHT)

    def clamp_camera(self, camera_x: int, camera_y: int) -> tuple[int, int]:
        return (
            _clamp(camera_x, 0, self.max_camera_x),
            _clamp(camera_y, 0, self.max_camera_y),
        )

    def render(
        self,
        *,
        camera_x: int,
        camera_y: int,
        flags: RenderFlags,
        spot_phase_degrees: int = 0,
        sprites: Sequence[WorldSprite] = (),
    ) -> bytes:
        camera_x, camera_y = self.clamp_camera(camera_x, camera_y)
        self.framebuffer.clear(0)

        self._draw_floor(camera_x, camera_y, use_dark_floor=flags.dark_mode)
        for sprite in sprites:
            self._draw_world_sprite(camera_x, camera_y, sprite)
        self._draw_walls(camera_x, camera_y)

        if flags.shadows:
            self._draw_level_shadows(camera_x, camera_y)
        if flags.light_effects:
            self._draw_spot_lights(camera_x, camera_y, spot_phase_degrees)

        return self.framebuffer.as_bytes()

    def _draw_floor(self, camera_x: int, camera_y: int, *, use_dark_floor: bool) -> None:
        sheet = self.dark_floor_sheet if use_dark_floor else self.floor_sheet
        self._draw_blocks(camera_x, camera_y, block_type=FLOOR_BLOCK_TYPE, sheet=sheet)

    def _draw_walls(self, camera_x: int, camera_y: int) -> None:
        self._draw_blocks(
            camera_x,
            camera_y,
            block_type=WALL_BLOCK_TYPE,
            sheet=self.wall_sheet,
            out_of_bounds_tile=19,
        )

    def _draw_blocks(
        self,
        camera_x: int,
        camera_y: int,
        *,
        block_type: int,
        sheet: bytes,
        out_of_bounds_tile: int | None = None,
    ) -> None:
        start_tile_x = camera_x // TILE_SIZE
        start_tile_y = camera_y // TILE_SIZE
        offset_x = camera_x % TILE_SIZE
        offset_y = camera_y % TILE_SIZE

        rows = (SCREEN_HEIGHT // TILE_SIZE) + 2
        cols = (SCREEN_WIDTH // TILE_SIZE) + 2

        for row in range(rows):
            tile_y = start_tile_y + row
            screen_y = row * TILE_SIZE - offset_y
            for col in range(cols):
                tile_x = start_tile_x + col
                screen_x = col * TILE_SIZE - offset_x

                if 0 <= tile_x < self.level.level_x_size and 0 <= tile_y < self.level.level_y_size:
                    block = self.level.blocks[tile_y * self.level.level_x_size + tile_x]
                    if block.type == block_type:
                        self._draw_tile(sheet=sheet, tile_num=block.num, screen_x=screen_x, screen_y=screen_y)
                elif out_of_bounds_tile is not None:
                    self._draw_tile(
                        sheet=sheet,
                        tile_num=out_of_bounds_tile,
                        screen_x=screen_x,
                        screen_y=screen_y,
                    )

    def _draw_tile(self, *, sheet: bytes, tile_num: int, screen_x: int, screen_y: int) -> None:
        tiles_per_row = SCREEN_WIDTH // TILE_SIZE
        tile_count = tiles_per_row * (SCREEN_HEIGHT // TILE_SIZE)
        tile = _clamp(tile_num, 0, tile_count - 1)

        src_x = (tile % tiles_per_row) * TILE_SIZE
        src_y = (tile // tiles_per_row) * TILE_SIZE
        self.framebuffer.blit_opaque(
            sheet,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            screen_x,
            screen_y,
            src_x=src_x,
            src_y=src_y,
            width=TILE_SIZE,
            height=TILE_SIZE,
        )

    def _draw_level_shadows(self, camera_x: int, camera_y: int) -> None:
        start_tile_x = camera_x // TILE_SIZE
        start_tile_y = camera_y // TILE_SIZE
        offset_x = camera_x % TILE_SIZE
        offset_y = camera_y % TILE_SIZE

        rows = (SCREEN_HEIGHT // TILE_SIZE) + 2
        cols = (SCREEN_WIDTH // TILE_SIZE) + 2

        for row in range(rows):
            tile_y = start_tile_y + row
            if tile_y < 0 or tile_y >= self.level.level_y_size:
                continue
            screen_y = row * TILE_SIZE - offset_y

            for col in range(cols):
                tile_x = start_tile_x + col
                if tile_x < 0 or tile_x >= self.level.level_x_size:
                    continue
                screen_x = col * TILE_SIZE - offset_x

                block = self.level.blocks[tile_y * self.level.level_x_size + tile_x]
                if block.shadow <= 0:
                    continue

                shadow_variant = _clamp(block.shadow - 1, 0, (SCREEN_WIDTH // TILE_SIZE) - 1)
                self.framebuffer.apply_shadow(
                    self.shadow_sheet,
                    SCREEN_WIDTH,
                    TILE_SIZE,
                    screen_x,
                    screen_y,
                    shadow_table=self.palette_tables.shadow_table,
                    src_x=shadow_variant * TILE_SIZE,
                    src_y=0,
                    width=TILE_SIZE,
                    height=TILE_SIZE,
                )

    def _draw_world_sprite(self, camera_x: int, camera_y: int, sprite: WorldSprite) -> None:
        screen_x = sprite.world_x - camera_x - sprite.anchor_x
        screen_y = sprite.world_y - camera_y - sprite.anchor_y
        if sprite.translucent:
            self.framebuffer.blit_translucent(
                sprite.pixels,
                sprite.width,
                sprite.height,
                screen_x,
                screen_y,
                trans_table=self.palette_tables.trans_table,
            )
            return

        self.framebuffer.blit_transparent(
            sprite.pixels,
            sprite.width,
            sprite.height,
            screen_x,
            screen_y,
        )

    def _draw_spot_lights(self, camera_x: int, camera_y: int, spot_phase_degrees: int) -> None:
        add = int(2.5 * math.sin(math.radians(spot_phase_degrees)) + 2)
        for spot in self.level.spots:
            size_index = _clamp(spot.size, 0, len(LIGHT_SIZES) - 1)
            mask = self.light_masks[size_index]
            mask_size = LIGHT_SIZES[size_index]

            screen_x = spot.x - camera_x - (mask_size // 2)
            screen_y = spot.y - camera_y - (mask_size // 2)
            self.framebuffer.apply_light(
                mask,
                mask_size,
                mask_size,
                screen_x,
                screen_y,
                light_table=self.palette_tables.normal_light_table,
                add=add,
            )

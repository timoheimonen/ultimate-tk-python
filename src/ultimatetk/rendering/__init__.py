"""Software rendering primitives for the Python refactor."""

from ultimatetk.rendering.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_SIZE
from ultimatetk.rendering.framebuffer import IndexedFrameBuffer
from ultimatetk.rendering.palette import build_rgb_palette, indexed_to_rgb24, write_indexed_ppm
from ultimatetk.rendering.software import (
    RenderFlags,
    SoftwareRenderer,
    WorldSprite,
    build_dark_floor_sheet,
    build_light_mask,
    build_light_masks,
    camera_from_player_start,
    extract_horizontal_sprite_frame,
    frame_digest,
)

__all__ = [
    "IndexedFrameBuffer",
    "RenderFlags",
    "SCREEN_HEIGHT",
    "SCREEN_WIDTH",
    "SoftwareRenderer",
    "TILE_SIZE",
    "WorldSprite",
    "build_dark_floor_sheet",
    "build_light_mask",
    "build_light_masks",
    "build_rgb_palette",
    "camera_from_player_start",
    "extract_horizontal_sprite_frame",
    "frame_digest",
    "indexed_to_rgb24",
    "write_indexed_ppm",
]

from __future__ import annotations

from typing import Sequence

from ultimatetk.formats.fnt import FontFile
from ultimatetk.rendering.constants import SCREEN_HEIGHT, SCREEN_WIDTH


UI_BG_COLOR = 13
UI_PANEL_COLOR = 8
UI_BORDER_COLOR = 98
UI_TEXT_COLOR = 113
UI_MUTED_COLOR = 76
UI_SELECTED_COLOR = 112
UI_SHADOW_COLOR = 6


def fallback_palette_bytes() -> bytes:
    palette = bytearray(256 * 3)
    for index in range(256):
        shade = min(63, index // 4)
        base = index * 3
        palette[base] = shade
        palette[base + 1] = shade
        palette[base + 2] = shade
    return bytes(palette)


def render_menu_frame(
    *,
    font: FontFile | None,
    selected_index: int,
    entries: Sequence[str],
) -> bytes:
    pixels = bytearray(SCREEN_WIDTH * SCREEN_HEIGHT)
    _fill_rect(pixels, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, UI_BG_COLOR)
    _fill_rect(pixels, 4, 4, SCREEN_WIDTH - 8, SCREEN_HEIGHT - 8, UI_SHADOW_COLOR)
    _fill_rect(pixels, 6, 6, SCREEN_WIDTH - 12, SCREEN_HEIGHT - 12, UI_PANEL_COLOR)
    _stroke_rect(pixels, 6, 6, SCREEN_WIDTH - 12, SCREEN_HEIGHT - 12, UI_BORDER_COLOR)

    _draw_text(pixels, font, 16, 18, "ULTIMATE TK", UI_TEXT_COLOR)
    _draw_text(pixels, font, 16, 30, "MAIN MENU", UI_MUTED_COLOR)

    base_y = 74
    step_y = 22
    for index, entry in enumerate(entries):
        y = base_y + (index * step_y)
        is_selected = index == selected_index
        if is_selected:
            _fill_rect(pixels, 58, y - 4, 204, 16, UI_SELECTED_COLOR)
            _stroke_rect(pixels, 58, y - 4, 204, 16, UI_BORDER_COLOR)

        marker = ">" if is_selected else " "
        text = f"{marker} {entry.upper()}"
        text_color = UI_PANEL_COLOR if is_selected else UI_TEXT_COLOR
        _draw_text(pixels, font, 70, y, text, text_color)

    _draw_text(pixels, font, 12, 180, "W/S OR A/D TO SELECT", UI_MUTED_COLOR)
    _draw_text(pixels, font, 12, 190, "SPACE/ENTER/TAB TO CONFIRM", UI_MUTED_COLOR)
    return bytes(pixels)


def render_progress_frame(
    *,
    font: FontFile | None,
    title: str,
    detail: str,
    hint: str,
) -> bytes:
    pixels = bytearray(SCREEN_WIDTH * SCREEN_HEIGHT)
    _fill_rect(pixels, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, UI_BG_COLOR)
    _fill_rect(pixels, 22, 56, SCREEN_WIDTH - 44, 88, UI_PANEL_COLOR)
    _stroke_rect(pixels, 22, 56, SCREEN_WIDTH - 44, 88, UI_BORDER_COLOR)

    _draw_text(pixels, font, 34, 74, title.upper(), UI_TEXT_COLOR)
    _draw_text(pixels, font, 34, 92, detail.upper(), UI_TEXT_COLOR)
    _draw_text(pixels, font, 34, 118, hint.upper(), UI_MUTED_COLOR)
    return bytes(pixels)


def _draw_text(
    pixels: bytearray,
    font: FontFile | None,
    x: int,
    y: int,
    text: str,
    color: int,
) -> None:
    if font is None or not text:
        return
    if color < 0 or color > 255:
        return

    glyph_width = font.glyph_width
    glyph_height = font.glyph_height
    cursor_x = x
    for char in text:
        glyph = font.glyph(ord(char) & 0xFF)
        glyph_index = 0
        for glyph_y in range(glyph_height):
            screen_y = y + glyph_y
            if screen_y < 0 or screen_y >= SCREEN_HEIGHT:
                glyph_index += glyph_width
                continue

            row_offset = screen_y * SCREEN_WIDTH
            for glyph_x in range(glyph_width):
                screen_x = cursor_x + glyph_x
                if screen_x < 0 or screen_x >= SCREEN_WIDTH:
                    glyph_index += 1
                    continue

                if glyph[glyph_index] > 0:
                    pixels[row_offset + screen_x] = color
                glyph_index += 1

        cursor_x += glyph_width
        if cursor_x >= SCREEN_WIDTH:
            break


def _fill_rect(
    pixels: bytearray,
    x: int,
    y: int,
    width: int,
    height: int,
    color: int,
) -> None:
    if width <= 0 or height <= 0:
        return
    if color < 0 or color > 255:
        return

    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(SCREEN_WIDTH, x + width)
    y1 = min(SCREEN_HEIGHT, y + height)
    if x0 >= x1 or y0 >= y1:
        return

    row_fill = bytes((color,)) * (x1 - x0)
    for row in range(y0, y1):
        row_start = row * SCREEN_WIDTH + x0
        pixels[row_start : row_start + (x1 - x0)] = row_fill


def _stroke_rect(
    pixels: bytearray,
    x: int,
    y: int,
    width: int,
    height: int,
    color: int,
) -> None:
    if width <= 1 or height <= 1:
        return
    _fill_rect(pixels, x, y, width, 1, color)
    _fill_rect(pixels, x, y + height - 1, width, 1, color)
    _fill_rect(pixels, x, y, 1, height, color)
    _fill_rect(pixels, x + width - 1, y, 1, height, color)

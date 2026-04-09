from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ultimatetk.formats._binary import BinaryReader


TRANS_TABLE_SIZE = 256 * 256
SHADOW_TABLE_SIZE = 256 * 16
LIGHT_TABLE_SIZE = 256 * 16
PALETTE_TAB_SIZE = TRANS_TABLE_SIZE + SHADOW_TABLE_SIZE + (4 * LIGHT_TABLE_SIZE)


@dataclass(frozen=True, slots=True)
class PaletteTables:
    trans_table: bytes
    shadow_table: bytes
    normal_light_table: bytes
    red_light_table: bytes
    yellow_light_table: bytes
    explo_light_table: bytes


def parse_palette_tab(data: bytes) -> PaletteTables:
    if len(data) != PALETTE_TAB_SIZE:
        raise ValueError(
            f"palette.tab must be exactly {PALETTE_TAB_SIZE} bytes, got {len(data)}",
        )

    reader = BinaryReader(data=data)
    trans_table = reader.read_bytes(TRANS_TABLE_SIZE)
    shadow_table = reader.read_bytes(SHADOW_TABLE_SIZE)
    normal_light = reader.read_bytes(LIGHT_TABLE_SIZE)
    red_light = reader.read_bytes(LIGHT_TABLE_SIZE)
    yellow_light = reader.read_bytes(LIGHT_TABLE_SIZE)
    explo_light = reader.read_bytes(LIGHT_TABLE_SIZE)

    return PaletteTables(
        trans_table=trans_table,
        shadow_table=shadow_table,
        normal_light_table=normal_light,
        red_light_table=red_light,
        yellow_light_table=yellow_light,
        explo_light_table=explo_light,
    )


def load_palette_tab(path: str | Path) -> PaletteTables:
    file_path = Path(path)
    return parse_palette_tab(file_path.read_bytes())

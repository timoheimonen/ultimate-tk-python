from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ultimatetk.formats._binary import BinaryReader, decode_c_string


DIFF_WEAPONS = 11
DIFF_BULLETS = 9
DIFF_ENEMIES = 8


@dataclass(frozen=True, slots=True)
class Block:
    type: int
    num: int
    shadow: int


@dataclass(frozen=True, slots=True)
class Spot:
    x: int
    y: int
    size: int


@dataclass(frozen=True, slots=True)
class Steam:
    x: int
    y: int
    angle: int
    speed: int


@dataclass(frozen=True, slots=True)
class GeneralLevelInfo:
    comment: str
    time_limit: int
    enemies: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CrateCounts:
    weapon_crates: tuple[int, ...]
    bullet_crates: tuple[int, ...]
    energy_crates: int


@dataclass(frozen=True, slots=True)
class CrateInfo:
    type1: int
    type2: int
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class LevelData:
    version: int
    level_x_size: int
    level_y_size: int
    blocks: tuple[Block, ...]
    player_start_x: tuple[int, int]
    player_start_y: tuple[int, int]
    spots: tuple[Spot, ...]
    steams: tuple[Steam, ...]
    general_info: GeneralLevelInfo
    normal_crate_counts: CrateCounts
    deathmatch_crate_counts: CrateCounts
    normal_crate_info: tuple[CrateInfo, ...]
    deathmatch_crate_info: tuple[CrateInfo, ...]


def parse_lev(data: bytes) -> LevelData:
    reader = BinaryReader(data=data)

    version = reader.read_i32_le()
    if version > 5:
        raise ValueError(f"invalid level version: {version}")

    level_x_size = reader.read_i32_le()
    level_y_size = reader.read_i32_le()
    if level_x_size <= 0 or level_y_size <= 0:
        raise ValueError("level dimensions must be positive")

    block_count = level_x_size * level_y_size
    blocks = tuple(
        Block(
            type=reader.read_i32_le(),
            num=reader.read_i32_le(),
            shadow=reader.read_i32_le(),
        )
        for _ in range(block_count)
    )

    start_x0 = reader.read_i32_le()
    start_y0 = reader.read_i32_le()
    start_x1 = reader.read_i32_le()
    start_y1 = reader.read_i32_le()
    player_start_x = (start_x0, start_x1)
    player_start_y = (start_y0, start_y1)

    spot_amount = reader.read_i32_le()
    if spot_amount < 0:
        raise ValueError("spot amount cannot be negative")
    spots = tuple(
        Spot(x=reader.read_i32_le(), y=reader.read_i32_le(), size=reader.read_i32_le())
        for _ in range(spot_amount)
    )

    steam_amount = reader.read_i32_le()
    if steam_amount < 0:
        raise ValueError("steam amount cannot be negative")
    steams = tuple(
        Steam(
            x=reader.read_i32_le(),
            y=reader.read_i32_le(),
            angle=reader.read_i32_le(),
            speed=reader.read_i32_le(),
        )
        for _ in range(steam_amount)
    )

    comment = decode_c_string(reader.read_bytes(20))
    time_limit = reader.read_i32_le()

    if version >= 4:
        enemies = tuple(reader.read_i32_array(DIFF_ENEMIES))
    else:
        old_enemies = reader.read_i32_array(DIFF_ENEMIES - 1)
        enemies = tuple(old_enemies) + (0,)

    if version == 1:
        weapons_count = DIFF_WEAPONS - 2
        bullets_count = DIFF_BULLETS - 2
    elif version == 2:
        weapons_count = DIFF_WEAPONS - 1
        bullets_count = DIFF_BULLETS - 1
    else:
        weapons_count = DIFF_WEAPONS
        bullets_count = DIFF_BULLETS

    normal_crates = CrateCounts(
        weapon_crates=reader.read_i32_array(weapons_count),
        bullet_crates=reader.read_i32_array(bullets_count),
        energy_crates=reader.read_i32_le(),
    )
    deathmatch_crates = CrateCounts(
        weapon_crates=reader.read_i32_array(weapons_count),
        bullet_crates=reader.read_i32_array(bullets_count),
        energy_crates=reader.read_i32_le(),
    )

    normal_crate_info: tuple[CrateInfo, ...] = ()
    deathmatch_crate_info: tuple[CrateInfo, ...] = ()
    if version >= 5:
        normal_crate_amount = reader.read_i32_le()
        if normal_crate_amount < 0:
            raise ValueError("normal crate amount cannot be negative")
        normal_crate_info = tuple(
            CrateInfo(
                type1=reader.read_i32_le(),
                type2=reader.read_i32_le(),
                x=reader.read_i32_le(),
                y=reader.read_i32_le(),
            )
            for _ in range(normal_crate_amount)
        )

        deathmatch_crate_amount = reader.read_i32_le()
        if deathmatch_crate_amount < 0:
            raise ValueError("deathmatch crate amount cannot be negative")
        deathmatch_crate_info = tuple(
            CrateInfo(
                type1=reader.read_i32_le(),
                type2=reader.read_i32_le(),
                x=reader.read_i32_le(),
                y=reader.read_i32_le(),
            )
            for _ in range(deathmatch_crate_amount)
        )

    general_info = GeneralLevelInfo(
        comment=comment,
        time_limit=time_limit,
        enemies=enemies,
    )

    return LevelData(
        version=version,
        level_x_size=level_x_size,
        level_y_size=level_y_size,
        blocks=blocks,
        player_start_x=player_start_x,
        player_start_y=player_start_y,
        spots=spots,
        steams=steams,
        general_info=general_info,
        normal_crate_counts=normal_crates,
        deathmatch_crate_counts=deathmatch_crates,
        normal_crate_info=normal_crate_info,
        deathmatch_crate_info=deathmatch_crate_info,
    )


def load_lev(path: str | Path) -> LevelData:
    file_path = Path(path)
    return parse_lev(file_path.read_bytes())

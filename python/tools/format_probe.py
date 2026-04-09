from __future__ import annotations

import argparse
from pathlib import Path
import sys


THIS_FILE = Path(__file__).resolve()
PYTHON_ROOT = THIS_FILE.parents[1]
SRC_ROOT = PYTHON_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.assets import GameDataRepository
from ultimatetk.core.paths import GamePaths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe parsed data from python/game_data")
    parser.add_argument("--efp", default="COOL.EFP", help="EFP filename in game_data/efps")
    parser.add_argument("--fnt", default="8X8.FNT", help="FNT filename in game_data/fnts")
    parser.add_argument("--episode", default="DEFAULT", help="Episode directory in game_data/levs")
    parser.add_argument("--lev", default="LEVEL1.LEV", help="LEV filename inside episode")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = GamePaths.discover()
    paths.validate_game_data_layout()
    repo = GameDataRepository(paths)

    palette = repo.load_palette_tables()
    print(f"palette.tab: trans={len(palette.trans_table)} shadow={len(palette.shadow_table)}")

    options = repo.try_load_options()
    if options is None:
        print("options.cfg: missing (this is allowed)")
    else:
        print(
            "options.cfg: "
            f"name1={options.name1!r} name2={options.name2!r} "
            f"music={options.music_volume} effects={options.effect_volume}",
        )

    efp = repo.load_efp(args.efp)
    print(f"{args.efp}: {efp.width}x{efp.height}, pixels={len(efp.pixels)}")

    fnt = repo.load_fnt(args.fnt)
    print(
        f"{args.fnt}: glyph={fnt.glyph_width}x{fnt.glyph_height}, "
        f"data={len(fnt.glyph_data)}",
    )

    lev = repo.load_lev(args.lev, episode=args.episode)
    print(
        f"{args.episode}/{args.lev}: v{lev.version}, size={lev.level_x_size}x{lev.level_y_size}, "
        f"spots={len(lev.spots)} steams={len(lev.steams)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

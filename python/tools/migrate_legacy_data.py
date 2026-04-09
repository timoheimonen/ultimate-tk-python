from __future__ import annotations

import argparse
from pathlib import Path
import shutil


DIR_MAP = {
    "EFPS": "efps",
    "FNTS": "fnts",
    "LEVS": "levs",
    "MUSIC": "music",
    "WAVS": "wavs",
}

FILE_MAP = {
    "PALETTE.TAB": "palette.tab",
    "OPTIONS.CFG": "options.cfg",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy legacy TK data into python/game_data",
    )
    parser.add_argument(
        "--legacy-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Path containing legacy EFPS/FNTS/LEVS/MUSIC/WAVS folders",
    )
    parser.add_argument(
        "--python-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to the python/ folder",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned operations without copying",
    )
    return parser.parse_args()


def _copy_dir(src: Path, dst: Path, dry_run: bool) -> None:
    if not src.is_dir():
        raise FileNotFoundError(f"missing source directory: {src}")

    if dry_run:
        print(f"[DRY-RUN] copy dir {src} -> {dst}")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"copied dir {src} -> {dst}")


def _copy_file(src: Path, dst: Path, dry_run: bool) -> None:
    if not src.is_file():
        raise FileNotFoundError(f"missing source file: {src}")

    if dry_run:
        print(f"[DRY-RUN] copy file {src} -> {dst}")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"copied file {src} -> {dst}")


def main() -> int:
    args = parse_args()
    legacy_root = args.legacy_root.expanduser().resolve()
    python_root = args.python_root.expanduser().resolve()
    game_data_root = python_root / "game_data"

    for src_name, dst_name in DIR_MAP.items():
        _copy_dir(legacy_root / src_name, game_data_root / dst_name, args.dry_run)

    for src_name, dst_name in FILE_MAP.items():
        _copy_file(legacy_root / src_name, game_data_root / dst_name, args.dry_run)

    print("migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

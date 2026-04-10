from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ultimatetk.core.paths import GamePaths
from ultimatetk.formats.efp import EfpImage, load_efp
from ultimatetk.formats.fnt import FontFile, load_fnt
from ultimatetk.formats.lev import LevelData, load_lev
from ultimatetk.formats.options_cfg import OptionsConfig, load_options_cfg
from ultimatetk.formats.palette_tab import PaletteTables, load_palette_tab


def _ensure_path_within_directory(path: Path, directory: Path) -> Path:
    resolved_directory = directory.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_directory)
    except ValueError as exc:
        raise FileNotFoundError(f"asset path escapes expected directory: {path}") from exc
    return path


def _resolve_case_insensitive(directory: Path, filename: str) -> Path:
    if not directory.is_dir():
        raise FileNotFoundError(f"directory not found: {directory}")

    exact = directory / filename
    if exact.exists():
        return _ensure_path_within_directory(exact, directory)

    needle = filename.lower()
    for entry in directory.iterdir():
        if entry.name.lower() == needle:
            return _ensure_path_within_directory(entry, directory)

    raise FileNotFoundError(f"file not found in {directory}: {filename}")


@dataclass(slots=True)
class GameDataRepository:
    paths: GamePaths

    @property
    def efps_dir(self) -> Path:
        return self.paths.game_data_root / "efps"

    @property
    def fnts_dir(self) -> Path:
        return self.paths.game_data_root / "fnts"

    @property
    def levs_dir(self) -> Path:
        return self.paths.game_data_root / "levs"

    @property
    def music_dir(self) -> Path:
        return self.paths.game_data_root / "music"

    @property
    def wavs_dir(self) -> Path:
        return self.paths.game_data_root / "wavs"

    @property
    def palette_tab_path(self) -> Path:
        return _resolve_case_insensitive(self.paths.game_data_root, "palette.tab")

    @property
    def options_cfg_path(self) -> Path:
        return _resolve_case_insensitive(self.paths.game_data_root, "options.cfg")

    def load_palette_tables(self) -> PaletteTables:
        return load_palette_tab(self.palette_tab_path)

    def load_options(self) -> OptionsConfig:
        return load_options_cfg(self.options_cfg_path)

    def try_load_options(self) -> OptionsConfig | None:
        try:
            return self.load_options()
        except FileNotFoundError:
            return None

    def load_efp(self, filename: str) -> EfpImage:
        path = _resolve_case_insensitive(self.efps_dir, filename)
        return load_efp(path)

    def load_fnt(self, filename: str) -> FontFile:
        path = _resolve_case_insensitive(self.fnts_dir, filename)
        return load_fnt(path)

    def load_lev(self, filename: str, episode: str | None = None) -> LevelData:
        if episode is None:
            directory = self.levs_dir
        else:
            directory = _resolve_case_insensitive(self.levs_dir, episode)
        path = _resolve_case_insensitive(directory, filename)
        return load_lev(path)

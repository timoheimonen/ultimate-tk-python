from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ultimatetk.core.constants import REQUIRED_GAME_DATA_DIRS


@dataclass(frozen=True, slots=True)
class GamePaths:
    python_root: Path
    game_data_root: Path
    runs_root: Path

    @classmethod
    def discover(cls, anchor_file: str | Path | None = None) -> "GamePaths":
        env_root = os.getenv("ULTIMATETK_PYTHON_ROOT")
        if env_root:
            python_root = Path(env_root).expanduser().resolve()
        else:
            if anchor_file is None:
                anchor = Path(__file__).resolve()
            else:
                anchor = Path(anchor_file).expanduser().resolve()
            python_root = anchor.parents[3]

        return cls(
            python_root=python_root,
            game_data_root=python_root / "game_data",
            runs_root=python_root / "runs",
        )

    def validate_game_data_layout(self) -> None:
        missing = []
        if not self.game_data_root.is_dir():
            missing.append(str(self.game_data_root))
        for dirname in REQUIRED_GAME_DATA_DIRS:
            directory = self.game_data_root / dirname
            if not directory.is_dir():
                missing.append(str(directory))

        if missing:
            joined = ", ".join(missing)
            raise FileNotFoundError(f"Missing required game data directories: {joined}")

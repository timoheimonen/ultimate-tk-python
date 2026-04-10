from __future__ import annotations

import json
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

    def validate_game_data_layout(self, enforce_manifest: bool = False) -> None:
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

        if enforce_manifest:
            self.validate_required_asset_manifest()

    def validate_required_asset_manifest(self) -> None:
        manifest_path = self.game_data_root / "asset_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Missing required asset manifest: {manifest_path}")

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid asset manifest JSON: {manifest_path}: {exc}") from exc

        required_files = manifest.get("required_files")
        if not isinstance(required_files, list) or not required_files:
            raise ValueError("asset manifest must contain a non-empty 'required_files' list")

        root_resolved = self.game_data_root.resolve()
        missing_files: list[str] = []
        for relative_path in required_files:
            if not isinstance(relative_path, str) or not relative_path.strip():
                raise ValueError("asset manifest 'required_files' entries must be non-empty strings")

            candidate = (self.game_data_root / relative_path).resolve()
            try:
                candidate.relative_to(root_resolved)
            except ValueError as exc:
                raise ValueError(
                    f"asset manifest entry escapes game_data root: {relative_path}",
                ) from exc

            if not candidate.is_file():
                missing_files.append(str(self.game_data_root / relative_path))

        if missing_files:
            joined = ", ".join(missing_files)
            raise FileNotFoundError(f"Missing required game data files: {joined}")

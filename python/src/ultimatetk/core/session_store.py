from __future__ import annotations

import json
from pathlib import Path

from ultimatetk.core.paths import GamePaths
from ultimatetk.core.state import SessionState


_SESSION_VERSION = 1
_PROFILE_DIRNAME = "profiles"
_PROFILE_FILENAME = "session.json"


def session_profile_path(paths: GamePaths) -> Path:
    return paths.runs_root / _PROFILE_DIRNAME / _PROFILE_FILENAME


def load_persisted_session(paths: GamePaths) -> SessionState | None:
    path = session_profile_path(paths)
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("session profile payload must be an object")

    version = _parse_non_negative_int(payload.get("version", _SESSION_VERSION))
    if version != _SESSION_VERSION:
        raise ValueError(f"unsupported session profile version: {version}")

    player_name_raw = payload.get("player_name", "Player1")
    player_name = player_name_raw.strip() if isinstance(player_name_raw, str) else ""
    if not player_name:
        player_name = "Player1"

    return SessionState(
        episode_index=_parse_non_negative_int(payload.get("episode_index", 0)),
        level_index=_parse_non_negative_int(payload.get("level_index", 0)),
        player_name=player_name,
    )


def save_persisted_session(paths: GamePaths, session: SessionState) -> None:
    path = session_profile_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": _SESSION_VERSION,
        "episode_index": _parse_non_negative_int(session.episode_index),
        "level_index": _parse_non_negative_int(session.level_index),
        "player_name": session.player_name.strip() if session.player_name.strip() else "Player1",
    }
    path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")


def _parse_non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(value.strip()))
        except ValueError as exc:
            raise ValueError(f"invalid integer field value: {value!r}") from exc
    raise ValueError(f"invalid integer field type: {type(value).__name__}")

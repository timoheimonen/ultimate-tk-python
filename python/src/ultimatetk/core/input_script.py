from __future__ import annotations

from ultimatetk.core.events import AppEvent, EventType, InputAction


_ACTION_ALIASES: dict[str, str] = {
    "LEFT": "TURN_LEFT",
    "RIGHT": "TURN_RIGHT",
    "UP": "MOVE_FORWARD",
    "DOWN": "MOVE_BACKWARD",
    "STRAFE": "STRAFE_MODIFIER",
    "LSTRAFE": "STRAFE_LEFT",
    "RSTRAFE": "STRAFE_RIGHT",
    "NEXT": "NEXT_WEAPON",
}


def parse_input_script(script: str | None) -> dict[int, tuple[AppEvent, ...]]:
    if script is None or script.strip() == "":
        return {}

    schedule: dict[int, list[AppEvent]] = {}
    entries = script.split(";")
    for raw_entry in entries:
        entry = raw_entry.strip()
        if not entry:
            continue

        frame_part, event_part = _split_entry(entry)
        frame = _parse_frame(frame_part)
        event = _parse_event_token(event_part)

        if frame not in schedule:
            schedule[frame] = []
        schedule[frame].append(event)

    return {frame: tuple(events) for frame, events in sorted(schedule.items())}


def _split_entry(entry: str) -> tuple[str, str]:
    if ":" not in entry:
        raise ValueError(
            f"invalid input-script entry '{entry}': expected '<frame>:<event>'",
        )
    frame_part, event_part = entry.split(":", 1)
    return frame_part.strip(), event_part.strip()


def _parse_frame(frame_part: str) -> int:
    try:
        frame = int(frame_part)
    except ValueError as exc:
        raise ValueError(f"invalid input-script frame '{frame_part}'") from exc
    if frame < 0:
        raise ValueError(f"input-script frame must be non-negative, got {frame}")
    return frame


def _parse_event_token(token: str) -> AppEvent:
    if token == "":
        raise ValueError("input-script event token cannot be empty")

    if token.startswith("+"):
        return AppEvent.action_pressed(_resolve_action(token[1:]))
    if token.startswith("-"):
        return AppEvent.action_released(_resolve_action(token[1:]))

    normalized = _normalize_name(token)
    if normalized == "QUIT":
        return AppEvent(type=EventType.QUIT)

    if normalized.startswith("WEAPON="):
        value = normalized.split("=", 1)[1]
        try:
            slot = int(value)
        except ValueError as exc:
            raise ValueError(f"invalid weapon slot in token '{token}'") from exc
        if slot < 0:
            raise ValueError(f"weapon slot must be non-negative, got {slot}")
        return AppEvent.weapon_select(slot)

    return AppEvent.action_pressed(_resolve_action(token))


def _resolve_action(token: str) -> InputAction:
    normalized = _normalize_name(token)
    alias = _ACTION_ALIASES.get(normalized)
    if alias is not None:
        normalized = alias

    try:
        return InputAction[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown input action '{token}'") from exc


def _normalize_name(name: str) -> str:
    return name.strip().replace("-", "_").replace(" ", "_").upper()

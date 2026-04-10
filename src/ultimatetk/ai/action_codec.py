from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ultimatetk.core.events import AppEvent, InputAction


HOLD_ACTIONS: tuple[InputAction, ...] = (
    InputAction.MOVE_FORWARD,
    InputAction.MOVE_BACKWARD,
    InputAction.TURN_LEFT,
    InputAction.TURN_RIGHT,
    InputAction.STRAFE_LEFT,
    InputAction.STRAFE_RIGHT,
    InputAction.SHOOT,
    InputAction.STRAFE_MODIFIER,
)

TRIGGER_ACTIONS: tuple[InputAction, ...] = (
    InputAction.NEXT_WEAPON,
    InputAction.TOGGLE_SHOP,
)

WEAPON_SELECT_SIZE = 13


def build_action_space() -> Any:
    try:
        from gymnasium import spaces
    except ModuleNotFoundError as exc:
        raise RuntimeError("gymnasium is required for action space creation") from exc

    return spaces.Dict(
        {
            "hold": spaces.MultiBinary(len(HOLD_ACTIONS)),
            "trigger": spaces.MultiBinary(len(TRIGGER_ACTIONS)),
            "weapon_select": spaces.Discrete(WEAPON_SELECT_SIZE),
        },
    )


@dataclass(slots=True)
class ActionCodec:
    _previous_hold: np.ndarray = field(
        default_factory=lambda: np.zeros(len(HOLD_ACTIONS), dtype=np.bool_),
    )

    def reset(self) -> None:
        self._previous_hold = np.zeros(len(HOLD_ACTIONS), dtype=np.bool_)

    def decode(self, action: dict[str, Any]) -> tuple[AppEvent, ...]:
        hold = _as_bool_vector(action.get("hold"), size=len(HOLD_ACTIONS))
        trigger = _as_bool_vector(action.get("trigger"), size=len(TRIGGER_ACTIONS))
        weapon_select = int(action.get("weapon_select", 0))

        events: list[AppEvent] = []

        for index, input_action in enumerate(HOLD_ACTIONS):
            now_pressed = bool(hold[index])
            was_pressed = bool(self._previous_hold[index])
            if now_pressed and not was_pressed:
                events.append(AppEvent.action_pressed(input_action))
            elif was_pressed and not now_pressed:
                events.append(AppEvent.action_released(input_action))

        self._previous_hold = hold

        for index, input_action in enumerate(TRIGGER_ACTIONS):
            if bool(trigger[index]):
                events.append(AppEvent.action_pressed(input_action))

        if weapon_select > 0:
            slot = weapon_select - 1
            events.append(AppEvent.weapon_select(slot))

        return tuple(events)


def _as_bool_vector(value: Any, *, size: int) -> np.ndarray:
    if value is None:
        return np.zeros(size, dtype=np.bool_)

    vector = np.asarray(value, dtype=np.int8).reshape(-1)
    result = np.zeros(size, dtype=np.bool_)
    if vector.size <= 0:
        return result

    limit = min(size, int(vector.size))
    result[:limit] = vector[:limit] != 0
    return result

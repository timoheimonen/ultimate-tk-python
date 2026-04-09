from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventType(str, Enum):
    QUIT = "quit"
    ACTION_PRESSED = "action_pressed"
    ACTION_RELEASED = "action_released"
    WEAPON_SELECT = "weapon_select"


class InputAction(str, Enum):
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    MOVE_FORWARD = "move_forward"
    MOVE_BACKWARD = "move_backward"
    SHOOT = "shoot"
    STRAFE_MODIFIER = "strafe_modifier"
    STRAFE_LEFT = "strafe_left"
    STRAFE_RIGHT = "strafe_right"
    NEXT_WEAPON = "next_weapon"


@dataclass(frozen=True, slots=True)
class AppEvent:
    type: EventType
    action: InputAction | None = None
    weapon_slot: int | None = None

    @classmethod
    def action_pressed(cls, action: InputAction) -> "AppEvent":
        return cls(type=EventType.ACTION_PRESSED, action=action)

    @classmethod
    def action_released(cls, action: InputAction) -> "AppEvent":
        return cls(type=EventType.ACTION_RELEASED, action=action)

    @classmethod
    def weapon_select(cls, weapon_slot: int) -> "AppEvent":
        return cls(type=EventType.WEAPON_SELECT, weapon_slot=weapon_slot)

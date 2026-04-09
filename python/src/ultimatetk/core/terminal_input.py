from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from ultimatetk.core.events import AppEvent, EventType, InputAction
from ultimatetk.formats.options_cfg import KeysConfig


TOKEN_ARROW_UP = "ARROW_UP"
TOKEN_ARROW_DOWN = "ARROW_DOWN"
TOKEN_ARROW_LEFT = "ARROW_LEFT"
TOKEN_ARROW_RIGHT = "ARROW_RIGHT"
TOKEN_TAB = "TAB"
TOKEN_ENTER = "ENTER"
TOKEN_ESCAPE = "ESC"
TOKEN_CTRL_C = "CTRL_C"


DEFAULT_TOKEN_TO_ACTION: dict[str, InputAction] = {
    "w": InputAction.MOVE_FORWARD,
    "W": InputAction.MOVE_FORWARD,
    TOKEN_ARROW_UP: InputAction.MOVE_FORWARD,
    "s": InputAction.MOVE_BACKWARD,
    "S": InputAction.MOVE_BACKWARD,
    TOKEN_ARROW_DOWN: InputAction.MOVE_BACKWARD,
    "a": InputAction.TURN_LEFT,
    "A": InputAction.TURN_LEFT,
    TOKEN_ARROW_LEFT: InputAction.TURN_LEFT,
    "d": InputAction.TURN_RIGHT,
    "D": InputAction.TURN_RIGHT,
    TOKEN_ARROW_RIGHT: InputAction.TURN_RIGHT,
    "q": InputAction.STRAFE_LEFT,
    "Q": InputAction.STRAFE_LEFT,
    "e": InputAction.STRAFE_RIGHT,
    "E": InputAction.STRAFE_RIGHT,
    "z": InputAction.STRAFE_MODIFIER,
    "Z": InputAction.STRAFE_MODIFIER,
    " ": InputAction.SHOOT,
    TOKEN_TAB: InputAction.NEXT_WEAPON,
}
TOKEN_TO_ACTION = DEFAULT_TOKEN_TO_ACTION


DEFAULT_TOKEN_TO_WEAPON_SLOT: dict[str, int] = {
    "`": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "0": 10,
    "-": 11,
    "=": 11,
}
TOKEN_TO_WEAPON_SLOT = DEFAULT_TOKEN_TO_WEAPON_SLOT


LEGACY_SCANCODE_TO_TOKEN: dict[int, str] = {
    1: TOKEN_ESCAPE,
    2: "1",
    3: "2",
    4: "3",
    5: "4",
    6: "5",
    7: "6",
    8: "7",
    9: "8",
    10: "9",
    11: "0",
    12: "-",
    13: "=",
    15: TOKEN_TAB,
    16: "q",
    17: "w",
    18: "e",
    19: "r",
    20: "t",
    21: "y",
    22: "u",
    23: "i",
    24: "o",
    25: "p",
    26: "[",
    27: "]",
    28: TOKEN_ENTER,
    30: "a",
    31: "s",
    32: "d",
    33: "f",
    34: "g",
    35: "h",
    36: "j",
    37: "k",
    38: "l",
    39: ";",
    40: "'",
    41: "`",
    43: "\\",
    44: "z",
    45: "x",
    46: "c",
    47: "v",
    48: "b",
    49: "n",
    50: "m",
    51: ",",
    52: ".",
    53: "/",
    57: " ",
    94: TOKEN_ARROW_UP,
    96: TOKEN_ARROW_LEFT,
    97: TOKEN_ARROW_RIGHT,
    99: TOKEN_ARROW_DOWN,
}


ACTION_TO_OPTIONS_FIELD: tuple[tuple[InputAction, str], ...] = (
    (InputAction.TURN_LEFT, "k_left"),
    (InputAction.TURN_RIGHT, "k_right"),
    (InputAction.MOVE_FORWARD, "k_up"),
    (InputAction.MOVE_BACKWARD, "k_down"),
    (InputAction.SHOOT, "k_shoot"),
    (InputAction.NEXT_WEAPON, "k_shift"),
    (InputAction.STRAFE_MODIFIER, "k_strafe"),
    (InputAction.STRAFE_LEFT, "k_lstrafe"),
    (InputAction.STRAFE_RIGHT, "k_rstrafe"),
)


QUIT_TOKENS = frozenset((TOKEN_ESCAPE, TOKEN_CTRL_C))


@dataclass(slots=True)
class TerminalKeyDecoder:
    _buffer: bytearray = field(default_factory=bytearray)

    def feed(self, data: bytes) -> tuple[str, ...]:
        if not data:
            return ()

        self._buffer.extend(data)
        tokens: list[str] = []
        while self._buffer:
            byte0 = self._buffer[0]
            if byte0 != 0x1B:
                tokens.append(_decode_byte(byte0))
                del self._buffer[0]
                continue

            if len(self._buffer) >= 3 and self._buffer[1] == 0x5B:
                arrow = self._buffer[2]
                if arrow == ord("A"):
                    tokens.append(TOKEN_ARROW_UP)
                    del self._buffer[:3]
                    continue
                if arrow == ord("B"):
                    tokens.append(TOKEN_ARROW_DOWN)
                    del self._buffer[:3]
                    continue
                if arrow == ord("C"):
                    tokens.append(TOKEN_ARROW_RIGHT)
                    del self._buffer[:3]
                    continue
                if arrow == ord("D"):
                    tokens.append(TOKEN_ARROW_LEFT)
                    del self._buffer[:3]
                    continue

            if len(self._buffer) == 1:
                break

            tokens.append(TOKEN_ESCAPE)
            del self._buffer[0]

        return tuple(tokens)

    def flush_pending_escape(self) -> tuple[str, ...]:
        if len(self._buffer) == 1 and self._buffer[0] == 0x1B:
            self._buffer.clear()
            return (TOKEN_ESCAPE,)
        return ()

    def reset(self) -> None:
        self._buffer.clear()


@dataclass(slots=True)
class TerminalInputMapper:
    hold_frames: int = 2
    token_to_action: dict[str, InputAction] = field(
        default_factory=lambda: dict(DEFAULT_TOKEN_TO_ACTION),
    )
    token_to_weapon_slot: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_TOKEN_TO_WEAPON_SLOT),
    )
    _active_until_frame: dict[InputAction, int] = field(default_factory=dict)

    def events_for_tokens(self, tokens: Sequence[str], frame: int) -> tuple[AppEvent, ...]:
        events: list[AppEvent] = []
        events.extend(self._release_expired(frame))

        for token in tokens:
            if token in QUIT_TOKENS:
                events.append(AppEvent(type=EventType.QUIT))
                continue

            weapon_slot = self.token_to_weapon_slot.get(token)
            if weapon_slot is not None:
                events.append(AppEvent.weapon_select(weapon_slot))
                continue

            action = self.token_to_action.get(token)
            if action is None:
                continue

            if action not in self._active_until_frame:
                events.append(AppEvent.action_pressed(action))
            self._active_until_frame[action] = frame + self.hold_frames

        return tuple(events)

    def reset(self) -> None:
        self._active_until_frame.clear()

    def _release_expired(self, frame: int) -> list[AppEvent]:
        expired = [
            action
            for action, until in self._active_until_frame.items()
            if until <= frame
        ]
        if not expired:
            return []

        for action in expired:
            del self._active_until_frame[action]
        expired.sort(key=lambda action: action.value)
        return [AppEvent.action_released(action) for action in expired]


def _decode_byte(byte_value: int) -> str:
    if byte_value == 0x03:
        return TOKEN_CTRL_C
    if byte_value == 0x09:
        return TOKEN_TAB
    if byte_value in (0x0A, 0x0D):
        return TOKEN_ENTER
    if 0x20 <= byte_value <= 0x7E:
        return chr(byte_value)
    return f"BYTE_{byte_value:02X}"


def build_token_to_action_from_legacy_keys(
    keys: KeysConfig | None,
    *,
    fallback_map: dict[str, InputAction] | None = None,
) -> tuple[dict[str, InputAction], tuple[int, ...]]:
    token_to_action = dict(fallback_map or DEFAULT_TOKEN_TO_ACTION)
    if keys is None:
        return token_to_action, ()

    unsupported_scancodes: set[int] = set()
    for action, field_name in ACTION_TO_OPTIONS_FIELD:
        scancode = int(getattr(keys, field_name))
        token = LEGACY_SCANCODE_TO_TOKEN.get(scancode)
        if token is None:
            unsupported_scancodes.add(scancode)
            continue

        _remove_action_bindings(token_to_action, action)
        _bind_token_to_action(token_to_action, token, action)

    return token_to_action, tuple(sorted(unsupported_scancodes))


def _remove_action_bindings(
    token_to_action: dict[str, InputAction],
    action: InputAction,
) -> None:
    keys_to_remove = [token for token, bound_action in token_to_action.items() if bound_action == action]
    for token in keys_to_remove:
        del token_to_action[token]


def _bind_token_to_action(
    token_to_action: dict[str, InputAction],
    token: str,
    action: InputAction,
) -> None:
    token_to_action[token] = action
    if len(token) == 1 and "a" <= token <= "z":
        token_to_action[token.upper()] = action

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventType(str, Enum):
    QUIT = "quit"


@dataclass(frozen=True, slots=True)
class AppEvent:
    type: EventType

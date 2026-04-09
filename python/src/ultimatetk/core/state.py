from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AppMode(str, Enum):
    BOOT = "boot"
    MAIN_MENU = "main_menu"
    GAMEPLAY = "gameplay"
    SHUTDOWN = "shutdown"


@dataclass(slots=True)
class RuntimeState:
    mode: AppMode = AppMode.BOOT
    running: bool = True
    simulation_frame: int = 0
    render_frame: int = 0
    elapsed_seconds: float = 0.0
    last_render_digest: int = 0
    last_render_width: int = 0
    last_render_height: int = 0


@dataclass(slots=True)
class SessionState:
    episode_index: int = 0
    level_index: int = 0
    player_name: str = "Player1"

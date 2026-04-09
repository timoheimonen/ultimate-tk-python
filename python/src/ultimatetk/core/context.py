from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.state import RuntimeState, SessionState


@dataclass(slots=True)
class GameContext:
    config: RuntimeConfig
    paths: GamePaths
    runtime: RuntimeState = field(default_factory=RuntimeState)
    session: SessionState = field(default_factory=SessionState)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("ultimatetk"))

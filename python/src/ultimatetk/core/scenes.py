from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent


class Scene(Protocol):
    name: str

    def on_enter(self, context: GameContext) -> None: ...

    def on_exit(self, context: GameContext) -> None: ...

    def handle_events(
        self,
        context: GameContext,
        events: Sequence[AppEvent],
    ) -> "SceneTransition | None": ...

    def update(self, context: GameContext, dt_seconds: float) -> "SceneTransition | None": ...

    def render(self, context: GameContext, alpha: float) -> None: ...


@dataclass(slots=True)
class SceneTransition:
    next_scene: Scene | None = None
    quit_requested: bool = False


class BaseScene:
    name = "base"

    def on_enter(self, context: GameContext) -> None:
        del context

    def on_exit(self, context: GameContext) -> None:
        del context

    def handle_events(
        self,
        context: GameContext,
        events: Sequence[AppEvent],
    ) -> SceneTransition | None:
        del context
        del events
        return None

    def update(self, context: GameContext, dt_seconds: float) -> SceneTransition | None:
        del context
        del dt_seconds
        return None

    def render(self, context: GameContext, alpha: float) -> None:
        del context
        del alpha


class SceneManager:
    def __init__(self, initial_scene: Scene, context: GameContext):
        self._context = context
        self._current_scene = initial_scene
        self._current_scene.on_enter(context)

    @property
    def current_scene_name(self) -> str:
        return self._current_scene.name

    def handle_events(self, events: Sequence[AppEvent]) -> None:
        transition = self._current_scene.handle_events(self._context, events)
        self._apply_transition(transition)

    def update(self, dt_seconds: float) -> None:
        transition = self._current_scene.update(self._context, dt_seconds)
        self._apply_transition(transition)

    def render(self, alpha: float) -> None:
        self._current_scene.render(self._context, alpha)

    def _apply_transition(self, transition: SceneTransition | None) -> None:
        if transition is None:
            return

        if transition.quit_requested:
            self._context.runtime.running = False
            return

        if transition.next_scene is None:
            return

        self._current_scene.on_exit(self._context)
        self._current_scene = transition.next_scene
        self._current_scene.on_enter(self._context)

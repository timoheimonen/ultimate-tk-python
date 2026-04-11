from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.scenes import SceneManager
from ultimatetk.systems.gameplay_scene import GameplayScene, GameplayStateView
from ultimatetk.systems.player_control import (
    PlayerState,
    bullet_ammo_capacities_snapshot,
    clamp_player_health_to_capacity,
)


WEAPON_MODE_NORMAL = "normal_mode"
WEAPON_MODE_TO_SLOT: dict[str, int] = {
    "fist": 0,
    "pistola": 1,
    "shotgun": 2,
    "uzi": 3,
    "auto_rifle": 4,
    "grenade_launcher": 5,
    "auto_grenadier": 6,
    "heavy_launcher": 7,
    "auto_shotgun": 8,
    "c4_activator": 9,
    "flame_thrower": 10,
    "mine_dropper": 11,
}


@dataclass(frozen=True, slots=True)
class PlayerCarryoverState:
    cash: int
    shield: int
    target_system_enabled: bool
    current_weapon: int
    weapons: tuple[bool, ...]
    bullets: tuple[int, ...]
    health: float


@dataclass(slots=True)
class TrainingRuntimeDriver:
    context: GameContext
    scene_manager: SceneManager
    fixed_dt_seconds: float
    render_enabled: bool
    weapon_mode: str = WEAPON_MODE_NORMAL
    _carryover: PlayerCarryoverState | None = None
    _last_gameplay_scene_id: int = 0

    @classmethod
    def create(
        cls,
        *,
        level_index: int = 0,
        target_tick_rate: int = 40,
        enforce_asset_manifest: bool = True,
        project_root: str | Path | None = None,
        render_enabled: bool = False,
        weapon_mode: str = WEAPON_MODE_NORMAL,
    ) -> "TrainingRuntimeDriver":
        if project_root is None:
            paths = GamePaths.discover()
        else:
            root = Path(project_root).expanduser().resolve()
            paths = GamePaths(
                python_root=root,
                game_data_root=root / "game_data",
                runs_root=root / "runs",
            )

        paths.validate_game_data_layout(enforce_manifest=enforce_asset_manifest)

        tick_rate = max(1, int(target_tick_rate))
        config = RuntimeConfig(
            target_tick_rate=tick_rate,
            max_frame_time_seconds=1.0 / float(tick_rate),
            max_updates_per_frame=1,
            autostart_gameplay=False,
            status_print_interval=0,
            platform="headless",
            session_auto_save=False,
            enforce_asset_manifest=enforce_asset_manifest,
        )

        context = GameContext(config=config, paths=paths)
        context.session.level_index = max(0, int(level_index))
        scene_manager = SceneManager(GameplayScene(), context)
        fixed_dt = 1.0 / float(tick_rate)

        driver = cls(
            context=context,
            scene_manager=scene_manager,
            fixed_dt_seconds=fixed_dt,
            render_enabled=bool(render_enabled),
            weapon_mode=_normalize_weapon_mode(weapon_mode),
        )
        driver._apply_training_overrides_to_current_scene()
        driver._refresh_carryover_snapshot()
        return driver

    def step(self, events: Sequence[AppEvent]) -> None:
        self.scene_manager.handle_events(events)
        self.scene_manager.update(self.fixed_dt_seconds)
        self.context.runtime.simulation_frame += 1

        self._restore_carryover_on_new_gameplay_scene()
        self._apply_training_overrides_to_current_scene()
        if self.render_enabled:
            self.scene_manager.render(0.0)
            self.context.runtime.render_frame += 1
        self.context.runtime.elapsed_seconds += self.fixed_dt_seconds
        self._refresh_carryover_snapshot()

    def gameplay_view(self) -> GameplayStateView | None:
        scene = self.scene_manager.current_scene
        if not isinstance(scene, GameplayScene):
            return None
        return scene.ai_state_view()

    def close(self) -> None:
        self.context.runtime.running = False

    def _refresh_carryover_snapshot(self) -> None:
        scene = self.scene_manager.current_scene
        if not isinstance(scene, GameplayScene):
            return

        player = getattr(scene, "_player", None)
        if not isinstance(player, PlayerState):
            return

        self._carryover = PlayerCarryoverState(
            cash=int(player.cash),
            shield=int(player.shield),
            target_system_enabled=bool(player.target_system_enabled),
            current_weapon=int(player.current_weapon),
            weapons=tuple(bool(value) for value in player.weapons),
            bullets=tuple(int(value) for value in player.bullets),
            health=float(player.health),
        )
        self._last_gameplay_scene_id = id(scene)

    def _apply_training_overrides_to_current_scene(self) -> None:
        if self.weapon_mode == WEAPON_MODE_NORMAL:
            return

        scene = self.scene_manager.current_scene
        if not isinstance(scene, GameplayScene):
            return

        slot = WEAPON_MODE_TO_SLOT[self.weapon_mode]

        crates = getattr(scene, "_crates", None)
        if isinstance(crates, list):
            crates.clear()
            self.context.runtime.crates_total = 0
            self.context.runtime.crates_alive = 0

        player = getattr(scene, "_player", None)
        if not isinstance(player, PlayerState):
            return

        player.infinite_ammo = True
        for index in range(len(player.weapons)):
            player.weapons[index] = index in (0, slot)
        player.current_weapon = slot

        capacities = bullet_ammo_capacities_snapshot()
        limit = min(len(player.bullets), len(capacities))
        for index in range(limit):
            player.bullets[index] = capacities[index]

    def _restore_carryover_on_new_gameplay_scene(self) -> None:
        scene = self.scene_manager.current_scene
        if not isinstance(scene, GameplayScene):
            return
        if self._carryover is None:
            return
        if id(scene) == self._last_gameplay_scene_id:
            return

        player = getattr(scene, "_player", None)
        if not isinstance(player, PlayerState):
            return

        player.cash = self._carryover.cash
        player.shield = self._carryover.shield
        player.target_system_enabled = self._carryover.target_system_enabled

        for index, owned in enumerate(self._carryover.weapons):
            if index >= len(player.weapons):
                break
            player.weapons[index] = bool(owned)
        if player.weapons:
            player.weapons[0] = True

        for index, units in enumerate(self._carryover.bullets):
            if index >= len(player.bullets):
                break
            player.bullets[index] = max(0, int(units))

        if 0 <= self._carryover.current_weapon < len(player.weapons) and player.weapons[self._carryover.current_weapon]:
            player.current_weapon = self._carryover.current_weapon
        else:
            player.current_weapon = 0

        player.health = max(0.0, self._carryover.health)
        clamp_player_health_to_capacity(player)

        self._last_gameplay_scene_id = id(scene)


def _normalize_weapon_mode(value: str) -> str:
    token = str(value).strip().lower()
    if token == "":
        return WEAPON_MODE_NORMAL
    if token == WEAPON_MODE_NORMAL:
        return WEAPON_MODE_NORMAL
    if token in WEAPON_MODE_TO_SLOT:
        return token
    choices = ", ".join((WEAPON_MODE_NORMAL, *WEAPON_MODE_TO_SLOT.keys()))
    raise ValueError(f"unknown weapon mode '{value}'. expected one of: {choices}")

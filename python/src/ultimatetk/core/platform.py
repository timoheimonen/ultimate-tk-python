from __future__ import annotations

from dataclasses import dataclass, field
import os
import select
import sys
from typing import Protocol, Sequence

from ultimatetk.assets import GameDataRepository
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent
from ultimatetk.core.terminal_input import (
    DEFAULT_TOKEN_TO_ACTION,
    TerminalInputMapper,
    TerminalKeyDecoder,
    build_token_to_action_from_legacy_keys,
)

try:
    import termios
    import tty
except ImportError:  # pragma: no cover - non-posix fallback
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]


class PlatformBackend(Protocol):
    def startup(self, context: GameContext) -> None: ...

    def poll_events(self) -> Sequence[AppEvent]: ...

    def present(self, context: GameContext, scene_name: str, alpha: float) -> None: ...

    def shutdown(self, context: GameContext) -> None: ...


@dataclass(slots=True)
class HeadlessPlatformBackend:
    status_print_interval: int = 0
    input_schedule: dict[int, tuple[AppEvent, ...]] | None = None
    _poll_frame: int = 0

    def startup(self, context: GameContext) -> None:
        self._poll_frame = 0
        context.logger.info("Headless runtime backend started")
        _log_input_schedule(context, self.input_schedule, backend_name="Headless")

    def poll_events(self) -> Sequence[AppEvent]:
        if self.input_schedule is None:
            self._poll_frame += 1
            return ()

        events = self.input_schedule.get(self._poll_frame, ())
        self._poll_frame += 1
        return events

    def present(self, context: GameContext, scene_name: str, alpha: float) -> None:
        del alpha
        _log_runtime_status(
            context,
            scene_name,
            status_print_interval=self.status_print_interval,
        )

    def shutdown(self, context: GameContext) -> None:
        context.logger.info("Headless runtime backend stopped")


@dataclass(slots=True)
class TerminalPlatformBackend:
    status_print_interval: int = 0
    hold_frames: int = 2
    input_schedule: dict[int, tuple[AppEvent, ...]] | None = None
    _poll_frame: int = 0
    _stdin_fd: int | None = None
    _saved_termios: list[object] | None = None
    _decoder: TerminalKeyDecoder = field(default_factory=TerminalKeyDecoder)
    _mapper: TerminalInputMapper = field(default_factory=TerminalInputMapper)

    def startup(self, context: GameContext) -> None:
        self._poll_frame = 0
        self._stdin_fd = None
        self._saved_termios = None
        self._decoder.reset()
        self._mapper = TerminalInputMapper(
            hold_frames=max(1, self.hold_frames),
            token_to_action=dict(DEFAULT_TOKEN_TO_ACTION),
        )

        self._load_options_bindings(context)

        context.logger.info("Terminal runtime backend started")
        _log_input_schedule(context, self.input_schedule, backend_name="Terminal")

        if termios is None or tty is None:
            context.logger.warning(
                "Terminal keyboard input unavailable (termios/tty missing)",
            )
            return

        if not sys.stdin.isatty():
            context.logger.warning(
                "Terminal backend has no TTY stdin, only scripted input is active",
            )
            return

        try:
            stdin_fd = sys.stdin.fileno()
            self._saved_termios = termios.tcgetattr(stdin_fd)
            tty.setcbreak(stdin_fd)
            self._stdin_fd = stdin_fd
        except OSError as exc:
            self._stdin_fd = None
            self._saved_termios = None
            context.logger.warning("Failed to initialize terminal keyboard input: %s", exc)
            return

        context.logger.info(
            "Terminal controls: WASD/arrows move-turn, Q/E strafe, TAB next weapon, "
            "` 1-0 - select weapon, SPACE shoot, ESC quits",
        )

    def poll_events(self) -> Sequence[AppEvent]:
        events: list[AppEvent] = []
        if self.input_schedule is not None:
            events.extend(self.input_schedule.get(self._poll_frame, ()))

        tokens = self._read_tokens()
        events.extend(self._mapper.events_for_tokens(tokens, self._poll_frame))

        self._poll_frame += 1
        return tuple(events)

    def present(self, context: GameContext, scene_name: str, alpha: float) -> None:
        del alpha
        _log_runtime_status(
            context,
            scene_name,
            status_print_interval=self.status_print_interval,
        )

    def shutdown(self, context: GameContext) -> None:
        if self._stdin_fd is not None and self._saved_termios is not None and termios is not None:
            try:
                termios.tcsetattr(self._stdin_fd, termios.TCSADRAIN, self._saved_termios)
            except OSError:
                pass

        self._stdin_fd = None
        self._saved_termios = None
        self._decoder.reset()
        self._mapper.reset()
        context.logger.info("Terminal runtime backend stopped")

    def _read_tokens(self) -> tuple[str, ...]:
        if self._stdin_fd is None:
            return ()

        tokens: list[str] = []
        while True:
            readable, _, _ = select.select([self._stdin_fd], [], [], 0.0)
            if not readable:
                break

            chunk = os.read(self._stdin_fd, 32)
            if not chunk:
                break
            tokens.extend(self._decoder.feed(chunk))

        tokens.extend(self._decoder.flush_pending_escape())
        return tuple(tokens)

    def _load_options_bindings(self, context: GameContext) -> None:
        repo = GameDataRepository(context.paths)
        try:
            options = repo.try_load_options()
        except ValueError as exc:
            context.logger.warning(
                "Terminal backend failed to parse options.cfg keybinds: %s",
                exc,
            )
            return

        if options is None:
            return

        token_map, unsupported = build_token_to_action_from_legacy_keys(
            options.keys1,
            fallback_map=self._mapper.token_to_action,
        )
        self._mapper.token_to_action = token_map

        if unsupported:
            codes = ",".join(str(code) for code in unsupported)
            context.logger.info(
                "Terminal backend kept fallback bindings for unsupported scancodes: %s",
                codes,
            )
        else:
            context.logger.info("Terminal backend loaded all player1 keybinds from options.cfg")


def _log_input_schedule(
    context: GameContext,
    schedule: dict[int, tuple[AppEvent, ...]] | None,
    *,
    backend_name: str,
) -> None:
    if not schedule:
        return
    event_count = sum(len(events) for events in schedule.values())
    context.logger.info(
        "%s input script loaded: %d frame(s), %d event(s)",
        backend_name,
        len(schedule),
        event_count,
    )


def _log_runtime_status(
    context: GameContext,
    scene_name: str,
    *,
    status_print_interval: int,
) -> None:
    if status_print_interval <= 0:
        return

    frame = context.runtime.render_frame
    if frame % status_print_interval != 0:
        return

    ammo_pools = context.runtime.player_ammo_pools
    ammo_pools_text = ",".join(str(units) for units in ammo_pools) if ammo_pools else "-"

    context.logger.info(
        "frame=%d mode=%s scene=%s sim=%d elapsed=%.3f render=%dx%d digest=%08x player=%d,%d angle=%03d weapon=%d ammo=%d/%d atype=%d apools=%s load=%d fire=%d shots=%d hits=%d hp=%d dead=%d ehits=%d eshots=%d edmg=%.1f proj=%d go=%d goticks=%d enemies=%d/%d kills=%d crates=%d/%d ckill=%d cget=%d",
        frame,
        context.runtime.mode.value,
        scene_name,
        context.runtime.simulation_frame,
        context.runtime.elapsed_seconds,
        context.runtime.last_render_width,
        context.runtime.last_render_height,
        context.runtime.last_render_digest,
        context.runtime.player_world_x,
        context.runtime.player_world_y,
        context.runtime.player_angle_degrees,
        context.runtime.player_weapon_slot,
        context.runtime.player_current_ammo_units,
        context.runtime.player_current_ammo_capacity,
        context.runtime.player_current_ammo_type_index,
        ammo_pools_text,
        context.runtime.player_load_count,
        context.runtime.player_fire_ticks,
        context.runtime.player_shots_fired_total,
        context.runtime.player_hits_total,
        context.runtime.player_health,
        context.runtime.player_dead,
        context.runtime.enemy_hits_total,
        context.runtime.enemy_shots_fired_total,
        context.runtime.enemy_damage_to_player_total,
        context.runtime.enemy_projectiles_active,
        context.runtime.game_over_active,
        context.runtime.game_over_ticks_remaining,
        context.runtime.enemies_alive,
        context.runtime.enemies_total,
        context.runtime.enemies_killed_by_player,
        context.runtime.crates_alive,
        context.runtime.crates_total,
        context.runtime.crates_destroyed_by_player,
        context.runtime.crates_collected_by_player,
    )

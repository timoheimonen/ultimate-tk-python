from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Sequence

from ultimatetk.core.boot_scene import BootScene
from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.events import AppEvent
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import EventType
from ultimatetk.core.fixed_step import FixedStepClock
from ultimatetk.core.input_script import parse_input_script
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.platform import HeadlessPlatformBackend, PlatformBackend, TerminalPlatformBackend
from ultimatetk.core.scenes import SceneManager
from ultimatetk.core.session_store import load_persisted_session, save_persisted_session, session_profile_path
from ultimatetk.core.state import AppMode


@dataclass(slots=True)
class GameApplication:
    context: GameContext
    scene_manager: SceneManager
    platform: PlatformBackend
    clock: FixedStepClock

    @classmethod
    def create(
        cls,
        config: RuntimeConfig,
        paths: GamePaths | None = None,
        platform: PlatformBackend | None = None,
    ) -> "GameApplication":
        resolved_paths = paths or GamePaths.discover()
        resolved_paths.validate_game_data_layout(enforce_manifest=config.enforce_asset_manifest)

        if config.session_load_on_start and config.session_new_on_start:
            raise ValueError("cannot combine session_load_on_start with session_new_on_start")

        context = GameContext(config=config, paths=resolved_paths)
        if config.session_new_on_start:
            context.logger.info("Starting new session profile")
            try:
                save_persisted_session(resolved_paths, context.session)
            except OSError as exc:
                context.logger.warning("Failed to write new session profile: %s", exc)
        elif config.session_load_on_start:
            try:
                persisted = load_persisted_session(resolved_paths)
            except (OSError, ValueError) as exc:
                persisted = None
                context.logger.warning("Failed to load session profile, using defaults: %s", exc)

            if persisted is None:
                context.logger.info("No persisted session profile found, using defaults")
            else:
                context.session = persisted
                context.logger.info(
                    "Loaded session profile level=%d episode=%d player=%s",
                    context.session.level_index + 1,
                    context.session.episode_index,
                    context.session.player_name,
                )

        scene_manager = SceneManager(BootScene(), context)
        input_schedule = parse_input_script(config.input_script)
        if platform is not None:
            active_platform = platform
        elif config.platform == "headless":
            active_platform = HeadlessPlatformBackend(
                status_print_interval=config.status_print_interval,
                input_schedule=input_schedule,
            )
        elif config.platform == "terminal":
            active_platform = TerminalPlatformBackend(
                status_print_interval=config.status_print_interval,
                hold_frames=config.terminal_hold_frames,
                input_schedule=input_schedule,
            )
        elif config.platform == "pygame":
            from ultimatetk.core.platform_pygame import PygamePlatformBackend

            active_platform = PygamePlatformBackend(
                status_print_interval=config.status_print_interval,
                input_schedule=input_schedule,
            )
        else:
            raise ValueError(f"unsupported platform backend: {config.platform}")
        clock = FixedStepClock(
            target_tick_rate=config.target_tick_rate,
            max_frame_time_seconds=config.max_frame_time_seconds,
        )
        return cls(
            context=context,
            scene_manager=scene_manager,
            platform=active_platform,
            clock=clock,
        )

    def run(self) -> int:
        self.platform.startup(self.context)
        self.clock.start()

        exit_code = 0
        try:
            while self.context.runtime.running:
                self.clock.tick()

                events = self.platform.poll_events()
                self._process_core_events(events)
                self.scene_manager.handle_events(events)

                updates = 0
                while self.clock.pop_update():
                    self.scene_manager.update(self.clock.fixed_dt_seconds)
                    self.context.runtime.simulation_frame += 1
                    updates += 1

                    if not self.context.runtime.running:
                        break

                    if updates >= self.context.config.max_updates_per_frame:
                        if self.clock.has_pending_update():
                            self.clock.drop_pending_time()
                            self.context.logger.warning(
                                "Exceeded max updates per frame, dropping pending simulation time",
                            )
                        break

                self.scene_manager.render(self.clock.interpolation_alpha)
                self.platform.present(
                    self.context,
                    self.scene_manager.current_scene_name,
                    self.clock.interpolation_alpha,
                )

                self.context.runtime.render_frame += 1
                self.context.runtime.elapsed_seconds = self.clock.total_seconds

                max_seconds = self.context.config.max_seconds
                if max_seconds is not None and self.context.runtime.elapsed_seconds >= max_seconds:
                    self.context.runtime.running = False

                if updates == 0:
                    wait_seconds = self.clock.fixed_dt_seconds - self.clock.accumulator_seconds
                    if wait_seconds > 0:
                        sleep(wait_seconds)

        except KeyboardInterrupt:
            exit_code = 130
            self.context.runtime.running = False
            self.context.logger.info("Interrupted by user")
        finally:
            if self.context.config.session_auto_save:
                try:
                    save_persisted_session(self.context.paths, self.context.session)
                    self.context.logger.info("Session profile saved to %s", session_profile_path(self.context.paths))
                except OSError as exc:
                    self.context.logger.warning("Failed to save session profile: %s", exc)
            self.context.runtime.mode = AppMode.SHUTDOWN
            self.platform.shutdown(self.context)

        return exit_code

    def _process_core_events(self, events: Sequence[AppEvent]) -> None:
        for event in events:
            if event.type == EventType.QUIT:
                self.context.runtime.running = False

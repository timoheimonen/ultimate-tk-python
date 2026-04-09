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
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.platform import HeadlessPlatformBackend, PlatformBackend
from ultimatetk.core.scenes import SceneManager
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
        resolved_paths.validate_game_data_layout()

        context = GameContext(config=config, paths=resolved_paths)
        scene_manager = SceneManager(BootScene(), context)
        active_platform = platform or HeadlessPlatformBackend(
            status_print_interval=config.status_print_interval,
        )
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
            self.context.runtime.mode = AppMode.SHUTDOWN
            self.platform.shutdown(self.context)

        return exit_code

    def _process_core_events(self, events: Sequence[AppEvent]) -> None:
        for event in events:
            if event.type == EventType.QUIT:
                self.context.runtime.running = False

from __future__ import annotations

import math

from ultimatetk.assets import GameDataRepository
from ultimatetk.core.context import GameContext
from ultimatetk.core.scenes import BaseScene
from ultimatetk.core.state import AppMode
from ultimatetk.rendering import (
    RenderFlags,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_SIZE,
    SoftwareRenderer,
    WorldSprite,
    camera_from_player_start,
    extract_horizontal_sprite_frame,
    frame_digest,
)


class GameplayScene(BaseScene):
    name = "gameplay"

    def __init__(self) -> None:
        self._ticks = 0
        self._renderer: SoftwareRenderer | None = None
        self._render_flags = RenderFlags()
        self._camera_x = 0
        self._camera_y = 0
        self._camera_base_x = 0
        self._camera_base_y = 0
        self._camera_max_x = 0
        self._camera_max_y = 0
        self._spot_phase = 0
        self._demo_sprites: tuple[WorldSprite, ...] = ()

    def on_enter(self, context: GameContext) -> None:
        context.runtime.mode = AppMode.GAMEPLAY
        context.runtime.last_render_digest = 0
        context.runtime.last_render_width = 0
        context.runtime.last_render_height = 0

        repo = GameDataRepository(context.paths)
        episode = "DEFAULT"
        level_name = f"LEVEL{max(1, context.session.level_index + 1)}.LEV"

        try:
            level = repo.load_lev(level_name, episode=episode)
        except FileNotFoundError:
            level_name = "LEVEL1.LEV"
            try:
                level = repo.load_lev(level_name, episode=episode)
            except FileNotFoundError as exc:
                context.logger.error("Gameplay level load failed: %s", exc)
                self._renderer = None
                return

        try:
            floor_sheet = repo.load_efp("FLOOR1.EFP")
            wall_sheet = repo.load_efp("WALLS1.EFP")
            shadow_sheet = repo.load_efp("SHADOWS.EFP")
            palette_tables = repo.load_palette_tables()
            self._renderer = SoftwareRenderer.from_assets(
                level=level,
                floor_image=floor_sheet,
                wall_image=wall_sheet,
                shadow_image=shadow_sheet,
                palette_tables=palette_tables,
            )
        except (FileNotFoundError, ValueError) as exc:
            self._renderer = None
            context.logger.error("Gameplay renderer initialization failed: %s", exc)
            return

        options = repo.try_load_options()
        if options is not None:
            self._render_flags = RenderFlags(
                dark_mode=bool(options.dark_mode),
                light_effects=bool(options.light_effects),
                shadows=bool(options.shadows),
            )

        camera_x, camera_y = camera_from_player_start(level)
        self._camera_x, self._camera_y = self._renderer.clamp_camera(camera_x, camera_y)
        self._camera_base_x = self._camera_x
        self._camera_base_y = self._camera_y
        self._camera_max_x = self._renderer.max_camera_x
        self._camera_max_y = self._renderer.max_camera_y

        spawn_x = level.player_start_x[0] * TILE_SIZE + 14
        spawn_y = level.player_start_y[0] * TILE_SIZE + 14
        self._demo_sprites = self._load_demo_sprites(repo, spawn_x=spawn_x, spawn_y=spawn_y)

        context.logger.info(
            "Gameplay render baseline ready: %s/%s dark=%s lights=%s shadows=%s",
            episode,
            level_name,
            self._render_flags.dark_mode,
            self._render_flags.light_effects,
            self._render_flags.shadows,
        )

    def update(self, context: GameContext, dt_seconds: float):
        del context
        del dt_seconds
        self._ticks += 1
        self._spot_phase = (self._spot_phase + 2) % 360

        orbit_x = int(14 * math.sin(self._ticks / 35.0))
        orbit_y = int(9 * math.cos(self._ticks / 42.0))
        self._camera_x = _clamp(self._camera_base_x + orbit_x, 0, self._camera_max_x)
        self._camera_y = _clamp(self._camera_base_y + orbit_y, 0, self._camera_max_y)
        return None

    def render(self, context: GameContext, alpha: float) -> None:
        del alpha
        if self._renderer is None:
            return

        pixels = self._renderer.render(
            camera_x=self._camera_x,
            camera_y=self._camera_y,
            flags=self._render_flags,
            spot_phase_degrees=self._spot_phase,
            sprites=self._demo_sprites,
        )

        context.runtime.last_render_width = SCREEN_WIDTH
        context.runtime.last_render_height = SCREEN_HEIGHT
        context.runtime.last_render_digest = frame_digest(pixels)

    def _load_demo_sprites(
        self,
        repo: GameDataRepository,
        *,
        spawn_x: int,
        spawn_y: int,
    ) -> tuple[WorldSprite, ...]:
        sprites: list[WorldSprite] = []

        try:
            crate_sheet = repo.load_efp("CRATES.EFP")
            crate_frame = extract_horizontal_sprite_frame(
                crate_sheet,
                frame_width=14,
                frame_height=14,
                frame_index=0,
            )
            sprites.append(
                WorldSprite(
                    world_x=spawn_x + 20,
                    world_y=spawn_y + 10,
                    width=14,
                    height=14,
                    pixels=crate_frame,
                    anchor_x=7,
                    anchor_y=7,
                    translucent=False,
                ),
            )
        except (FileNotFoundError, ValueError):
            pass

        try:
            target = repo.load_efp("TARGET.EFP")
            sprites.append(
                WorldSprite(
                    world_x=spawn_x,
                    world_y=spawn_y,
                    width=target.width,
                    height=target.height,
                    pixels=target.pixels,
                    anchor_x=target.width // 2,
                    anchor_y=target.height // 2,
                    translucent=True,
                ),
            )
        except FileNotFoundError:
            pass

        return tuple(sprites)


def _clamp(value: int, low: int, high: int) -> int:
    if value < low:
        return low
    if value > high:
        return high
    return value

from __future__ import annotations

from typing import Sequence

from ultimatetk.assets import GameDataRepository
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent, EventType, InputAction
from ultimatetk.core.scenes import BaseScene
from ultimatetk.core.state import AppMode
from ultimatetk.formats.efp import EfpImage
from ultimatetk.formats.lev import LevelData
from ultimatetk.rendering import (
    RenderFlags,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SoftwareRenderer,
    WorldSprite,
    extract_horizontal_sprite_frame,
    frame_digest,
)
from ultimatetk.systems.player_control import (
    PLAYER_CENTER_OFFSET,
    PlayerState,
    aim_point_from_player,
    apply_player_controls,
    follow_player_camera,
    spawn_player_from_level,
)


class GameplayScene(BaseScene):
    name = "gameplay"

    def __init__(self) -> None:
        self._renderer: SoftwareRenderer | None = None
        self._level: LevelData | None = None
        self._render_flags = RenderFlags()
        self._camera_x = 0
        self._camera_y = 0
        self._camera_max_x = 0
        self._camera_max_y = 0
        self._spot_phase = 0

        self._player: PlayerState | None = None
        self._held_actions: set[InputAction] = set()
        self._cycle_weapon_requested = False
        self._pending_weapon_slot: int | None = None

        self._static_sprites: tuple[WorldSprite, ...] = ()
        self._target_pixels: bytes | None = None
        self._target_width = 0
        self._target_height = 0
        self._rambo_frames: tuple[bytes, ...] = ()

    def on_enter(self, context: GameContext) -> None:
        context.runtime.mode = AppMode.GAMEPLAY
        context.runtime.last_render_digest = 0
        context.runtime.last_render_width = 0
        context.runtime.last_render_height = 0
        context.runtime.player_world_x = 0
        context.runtime.player_world_y = 0
        context.runtime.player_angle_degrees = 0
        context.runtime.player_weapon_slot = 0

        self._held_actions.clear()
        self._cycle_weapon_requested = False
        self._pending_weapon_slot = None
        self._target_pixels = None
        self._target_width = 0
        self._target_height = 0
        self._rambo_frames = ()
        self._static_sprites = ()
        self._spot_phase = 0
        self._render_flags = RenderFlags()

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
                self._level = None
                self._player = None
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
            self._level = None
            self._player = None
            context.logger.error("Gameplay renderer initialization failed: %s", exc)
            return

        self._level = level
        self._player = spawn_player_from_level(level)

        options = repo.try_load_options()
        if options is not None:
            self._render_flags = RenderFlags(
                dark_mode=bool(options.dark_mode),
                light_effects=bool(options.light_effects),
                shadows=bool(options.shadows),
            )

        player = self._player
        camera_x = int(player.center_x) - (SCREEN_WIDTH // 2)
        camera_y = int(player.center_y) - (SCREEN_HEIGHT // 2)
        self._camera_x, self._camera_y = self._renderer.clamp_camera(camera_x, camera_y)
        self._camera_max_x = self._renderer.max_camera_x
        self._camera_max_y = self._renderer.max_camera_y

        self._static_sprites = self._load_static_sprites(repo, player=player)
        self._target_pixels, self._target_width, self._target_height = self._load_target_sprite(repo)
        self._rambo_frames = self._load_rambo_frames(repo)

        self._publish_player_runtime_state(context)
        context.logger.info(
            "Gameplay phase-4 controls ready: %s/%s dark=%s lights=%s shadows=%s",
            episode,
            level_name,
            self._render_flags.dark_mode,
            self._render_flags.light_effects,
            self._render_flags.shadows,
        )

    def on_exit(self, context: GameContext) -> None:
        del context
        self._held_actions.clear()
        self._cycle_weapon_requested = False
        self._pending_weapon_slot = None

    def handle_events(self, context: GameContext, events: Sequence[AppEvent]) -> None:
        del context
        for event in events:
            if event.type == EventType.ACTION_PRESSED and event.action is not None:
                if event.action == InputAction.NEXT_WEAPON:
                    self._cycle_weapon_requested = True
                else:
                    self._held_actions.add(event.action)
                continue

            if event.type == EventType.ACTION_RELEASED and event.action is not None:
                if event.action != InputAction.NEXT_WEAPON:
                    self._held_actions.discard(event.action)
                continue

            if event.type == EventType.WEAPON_SELECT and event.weapon_slot is not None:
                self._pending_weapon_slot = event.weapon_slot

        return None

    def update(self, context: GameContext, dt_seconds: float) -> None:
        del dt_seconds
        if self._renderer is None or self._level is None or self._player is None:
            return None

        apply_player_controls(
            self._player,
            self._level,
            self._held_actions,
            cycle_weapon=self._cycle_weapon_requested,
            select_weapon_slot=self._pending_weapon_slot,
        )
        self._cycle_weapon_requested = False
        self._pending_weapon_slot = None

        self._spot_phase = (self._spot_phase + 2) % 360
        self._camera_x, self._camera_y = follow_player_camera(
            camera_x=self._camera_x,
            camera_y=self._camera_y,
            player=self._player,
            max_camera_x=self._camera_max_x,
            max_camera_y=self._camera_max_y,
        )

        self._publish_player_runtime_state(context)
        return None

    def render(self, context: GameContext, alpha: float) -> None:
        del alpha
        if self._renderer is None:
            return

        sprites = self._compose_world_sprites()
        pixels = self._renderer.render(
            camera_x=self._camera_x,
            camera_y=self._camera_y,
            flags=self._render_flags,
            spot_phase_degrees=self._spot_phase,
            sprites=sprites,
        )

        context.runtime.last_render_width = SCREEN_WIDTH
        context.runtime.last_render_height = SCREEN_HEIGHT
        context.runtime.last_render_digest = frame_digest(pixels)

    def _compose_world_sprites(self) -> tuple[WorldSprite, ...]:
        sprites = list(self._static_sprites)
        if self._player is None:
            return tuple(sprites)

        if self._rambo_frames:
            angle_index = (self._player.angle // 9) % len(self._rambo_frames)
            sprites.append(
                WorldSprite(
                    world_x=int(self._player.center_x),
                    world_y=int(self._player.center_y),
                    width=28,
                    height=28,
                    pixels=self._rambo_frames[angle_index],
                    anchor_x=PLAYER_CENTER_OFFSET,
                    anchor_y=PLAYER_CENTER_OFFSET,
                    translucent=False,
                ),
            )

        if self._target_pixels is not None:
            target_x, target_y = aim_point_from_player(self._player)
            sprites.append(
                WorldSprite(
                    world_x=target_x,
                    world_y=target_y,
                    width=self._target_width,
                    height=self._target_height,
                    pixels=self._target_pixels,
                    anchor_x=self._target_width // 2,
                    anchor_y=self._target_height // 2,
                    translucent=True,
                ),
            )

        return tuple(sprites)

    def _load_static_sprites(self, repo: GameDataRepository, *, player: PlayerState) -> tuple[WorldSprite, ...]:
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
                    world_x=int(player.center_x) + 20,
                    world_y=int(player.center_y) + 10,
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

        return tuple(sprites)

    def _load_target_sprite(self, repo: GameDataRepository) -> tuple[bytes | None, int, int]:
        try:
            target = repo.load_efp("TARGET.EFP")
            return target.pixels, target.width, target.height
        except FileNotFoundError:
            return None, 0, 0

    def _load_rambo_frames(self, repo: GameDataRepository) -> tuple[bytes, ...]:
        try:
            rambo_sheet = repo.load_efp("RAMBO2.EFP")
        except FileNotFoundError:
            return ()

        try:
            return _extract_rambo_frames(rambo_sheet, animation_row=1)
        except ValueError:
            return ()

    def _publish_player_runtime_state(self, context: GameContext) -> None:
        if self._player is None:
            context.runtime.player_world_x = 0
            context.runtime.player_world_y = 0
            context.runtime.player_angle_degrees = 0
            context.runtime.player_weapon_slot = 0
            return

        context.runtime.player_world_x = int(self._player.center_x)
        context.runtime.player_world_y = int(self._player.center_y)
        context.runtime.player_angle_degrees = self._player.angle
        context.runtime.player_weapon_slot = self._player.current_weapon


def _extract_rambo_frames(image: EfpImage, *, animation_row: int) -> tuple[bytes, ...]:
    frame_width = 28
    frame_height = 28
    frame_stride = 29

    row_y = 1 + (animation_row * frame_stride)
    if row_y < 0 or row_y + frame_height > image.height:
        raise ValueError("invalid rambo animation row")

    angle_frames = image.width // frame_stride
    if angle_frames <= 0:
        raise ValueError("rambo sprite sheet has no angle frames")

    frames: list[bytes] = []
    for angle in range(angle_frames):
        src_x = 1 + (angle * frame_stride)
        if src_x + frame_width > image.width:
            break

        frame = bytearray(frame_width * frame_height)
        for row in range(frame_height):
            src_start = (row_y + row) * image.width + src_x
            dst_start = row * frame_width
            frame[dst_start : dst_start + frame_width] = image.pixels[src_start : src_start + frame_width]
        frames.append(bytes(frame))

    if not frames:
        raise ValueError("failed to extract rambo angle frames")
    return tuple(frames)

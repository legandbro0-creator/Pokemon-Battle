"""Sprite and icon loading for the Pygame front-end.

Asset layout (all PNG, RGBA, produced from the supplied sprite packs):

    assets/pokemon/front/<dex>.png   Gen III FireRed/LeafGreen front sprites, 64x64, dex 1-151
    assets/pokemon/back/<dex>.png    Gen III FireRed/LeafGreen back sprites,  64x64, dex 1-151
    assets/items/<item-id>.png       30x30 item icons (item ids match engine/content.py ITEMS)

Every lookup degrades gracefully: a missing file returns ``None`` and the caller falls back to
its old drawing code, so a missing asset can never crash the interface.
"""
from __future__ import annotations
from pathlib import Path
import pygame

ASSETS = Path(__file__).resolve().parents[1] / "assets"


class SpriteBook:
    def __init__(self, root: Path = ASSETS):
        self.root = Path(root)
        self._raw: dict[Path, pygame.Surface | None] = {}
        self._cache: dict[tuple, object] = {}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def window_icon() -> pygame.Surface | None:
        """Poke Ball icon for the window; loaded without convert_alpha (no display needed yet)."""
        try:
            return pygame.transform.scale(pygame.image.load(str(ASSETS / "items" / "poke-ball.png")), (32, 32))
        except (pygame.error, FileNotFoundError, OSError):
            return None

    def _load(self, path: Path) -> pygame.Surface | None:
        if path not in self._raw:
            try:
                self._raw[path] = pygame.image.load(str(path)).convert_alpha()
            except (pygame.error, FileNotFoundError, OSError):
                self._raw[path] = None
        return self._raw[path]

    @staticmethod
    def _resize(surface: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
        # Nearest-neighbour when enlarging keeps pixel art crisp; smoothscale when shrinking.
        if size[0] >= surface.get_width() and size[1] >= surface.get_height():
            return pygame.transform.scale(surface, size)
        return pygame.transform.smoothscale(surface, size)

    # ---------------------------------------------------------------- pokemon
    def pokemon(self, dex: int, view: str = "front", scale: float = 2.0, *, faded: bool = False):
        """Scaled full-canvas sprite plus its 'feet' point (bottom-centre of the opaque pixels).

        Keeping the full 64x64 canvas means species keep their natural relative size
        (a Pidgey stays small, an Onix stays big).
        """
        key = ("mon", dex, view, scale, faded)
        if key in self._cache:
            return self._cache[key]
        raw = self._load(self.root / "pokemon" / view / f"{dex}.png")
        result = None
        if raw is not None:
            bounds = raw.get_bounding_rect()
            size = (max(1, round(raw.get_width() * scale)), max(1, round(raw.get_height() * scale)))
            surface = self._resize(raw, size)
            if faded:
                surface.set_alpha(105)
            result = (surface, (round(bounds.centerx * scale), round(bounds.bottom * scale)))
        self._cache[key] = result
        return result

    def draw_pokemon(self, target: pygame.Surface, dex: int, view: str, feet_pos: tuple[int, int],
                     scale: float, *, faded: bool = False) -> bool:
        entry = self.pokemon(dex, view, scale, faded=faded)
        if entry is None:
            return False
        surface, (fx, fy) = entry
        target.blit(surface, (feet_pos[0] - fx, feet_pos[1] - fy))
        return True

    def pokemon_icon(self, dex: int, size: int, view: str = "front") -> pygame.Surface | None:
        """Square icon: the sprite cropped to its visible pixels and fitted into size x size."""
        key = ("icon", dex, view, size)
        if key in self._cache:
            return self._cache[key]
        raw = self._load(self.root / "pokemon" / view / f"{dex}.png")
        icon = None
        if raw is not None:
            bounds = raw.get_bounding_rect()
            if bounds.w > 0 and bounds.h > 0:
                crop = raw.subsurface(bounds).copy()
                factor = min(size / bounds.w, size / bounds.h)
                new_size = (max(1, round(bounds.w * factor)), max(1, round(bounds.h * factor)))
                scaled = self._resize(crop, new_size)
                icon = pygame.Surface((size, size), pygame.SRCALPHA)
                icon.blit(scaled, scaled.get_rect(center=(size // 2, size // 2)))
        self._cache[key] = icon
        return icon

    # ------------------------------------------------------------------ items
    def item(self, item_id: str, size: int = 24, *, dim: bool = False) -> pygame.Surface | None:
        """Item icon scaled to size x size; ``dim`` darkens it (used for fainted party balls)."""
        key = ("item", item_id, size, dim)
        if key in self._cache:
            return self._cache[key]
        raw = self._load(self.root / "items" / f"{item_id}.png")
        icon = None
        if raw is not None:
            icon = self._resize(raw, (size, size))
            if dim:
                icon = icon.copy()
                icon.fill((75, 75, 85, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self._cache[key] = icon
        return icon

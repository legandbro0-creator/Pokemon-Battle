from __future__ import annotations
from pathlib import Path
from engine.content import ITEMS, SPECIES

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def test_every_gen1_species_has_front_and_back_sprite():
    for species in SPECIES.values():
        assert (ASSETS / "pokemon" / "front" / f"{species.dex}.png").is_file(), f"front sprite missing for #{species.dex}"
        assert (ASSETS / "pokemon" / "back" / f"{species.dex}.png").is_file(), f"back sprite missing for #{species.dex}"


def test_every_engine_item_and_ui_icon_exists():
    for item_id in [*ITEMS, "poke-ball", "mega-ring"]:
        assert (ASSETS / "items" / f"{item_id}.png").is_file(), f"item icon missing: {item_id}"


def test_sprite_book_loads_headless():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gui.sprites import SpriteBook
    pygame.init(); pygame.display.set_mode((64, 64))
    book = SpriteBook()
    assert book.pokemon(6, "front", 2.5) is not None and book.pokemon(6, "back", 3) is not None
    assert book.pokemon_icon(151, 38).get_size() == (38, 38)
    assert book.item("leftovers", 24).get_size() == (24, 24)
    assert book.pokemon(999) is None and book.item("not-an-item") is None  # graceful fallback

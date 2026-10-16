"""Offline content loader and the verified move/item subset used by milestone 1.

The roster is complete (151 Gen I species). The move execution catalog deliberately has a
smaller, tested subset; moves outside that catalog are not offered by the prototype yet.
"""
from __future__ import annotations
import json
from pathlib import Path
from .models import Category, Item, Move, Nature, Pokemon, MoveSlot, Species, Status
from .data_models import SpeciesRecord

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def _move(id: str, name: str, type: str, category: Category, power: int = 0, **kwargs) -> Move:
    return Move(id=id, name=name, type=type, category=category, power=power, **kwargs)

# Values follow current main-series move data for this deliberately supported execution set.
MOVES: dict[str, Move] = {
    "tackle": _move("tackle", "Tackle", "normal", Category.PHYSICAL, 40, pp=35, contact=True),
    "quick-attack": _move("quick-attack", "Quick Attack", "normal", Category.PHYSICAL, 40, pp=30, priority=1, contact=True),
    "body-slam": _move("body-slam", "Body Slam", "normal", Category.PHYSICAL, 85, pp=15, contact=True, effect="status", effect_chance=30, status=Status.PARALYSIS),
    "flamethrower": _move("flamethrower", "Flamethrower", "fire", Category.SPECIAL, 90, pp=15, effect="status", effect_chance=10, status=Status.BURN),
    "fire-punch": _move("fire-punch", "Fire Punch", "fire", Category.PHYSICAL, 75, pp=15, contact=True, effect="status", effect_chance=10, status=Status.BURN),
    "thunderbolt": _move("thunderbolt", "Thunderbolt", "electric", Category.SPECIAL, 90, pp=15, effect="status", effect_chance=10, status=Status.PARALYSIS),
    "volt-switch": _move("volt-switch", "Volt Switch", "electric", Category.SPECIAL, 70, pp=20, effect="pivot"),
    "surf": _move("surf", "Surf", "water", Category.SPECIAL, 90, pp=15),
    "waterfall": _move("waterfall", "Waterfall", "water", Category.PHYSICAL, 80, pp=15, contact=True, effect="flinch", effect_chance=20),
    "ice-beam": _move("ice-beam", "Ice Beam", "ice", Category.SPECIAL, 90, pp=10, effect="freeze", effect_chance=10),
    "ice-fang": _move("ice-fang", "Ice Fang", "ice", Category.PHYSICAL, 65, pp=15, accuracy=95, contact=True, effect="flinch", effect_chance=10),
    "earthquake": _move("earthquake", "Earthquake", "ground", Category.PHYSICAL, 100, pp=10),
    "psychic": _move("psychic", "Psychic", "psychic", Category.SPECIAL, 90, pp=10, effect="lower", effect_chance=10, stat_changes=(("spd", -1),)),
    "shadow-ball": _move("shadow-ball", "Shadow Ball", "ghost", Category.SPECIAL, 80, pp=15, effect="lower", effect_chance=20, stat_changes=(("spd", -1),)),
    "sludge-bomb": _move("sludge-bomb", "Sludge Bomb", "poison", Category.SPECIAL, 90, pp=10, effect="status", effect_chance=30, status=Status.POISON),
    "giga-drain": _move("giga-drain", "Giga Drain", "grass", Category.SPECIAL, 75, pp=10, drain_fraction=0.5),
    "energy-ball": _move("energy-ball", "Energy Ball", "grass", Category.SPECIAL, 90, pp=10, effect="lower", effect_chance=10, stat_changes=(("spd", -1),)),
    "rock-slide": _move("rock-slide", "Rock Slide", "rock", Category.PHYSICAL, 75, pp=10, accuracy=90, effect="flinch", effect_chance=30),
    "brick-break": _move("brick-break", "Brick Break", "fighting", Category.PHYSICAL, 75, pp=15, contact=True),
    "crunch": _move("crunch", "Crunch", "dark", Category.PHYSICAL, 80, pp=15, contact=True, effect="lower", effect_chance=20, stat_changes=(("def", -1),)),
    "dragon-claw": _move("dragon-claw", "Dragon Claw", "dragon", Category.PHYSICAL, 80, pp=15, contact=True),
    "aura-sphere": _move("aura-sphere", "Aura Sphere", "fighting", Category.SPECIAL, 80, pp=20, accuracy=None),
    "focus-blast": _move("focus-blast", "Focus Blast", "fighting", Category.SPECIAL, 120, pp=5, accuracy=70, effect="lower", effect_chance=10, stat_changes=(("spd", -1),)),
    "air-slash": _move("air-slash", "Air Slash", "flying", Category.SPECIAL, 75, pp=15, effect="flinch", effect_chance=30),
    "dragon-pulse": _move("dragon-pulse", "Dragon Pulse", "dragon", Category.SPECIAL, 85, pp=10),
    "swords-dance": _move("swords-dance", "Swords Dance", "normal", Category.STATUS, pp=20, effect="boost", target="self", stat_changes=(("atk", 2),)),
    "calm-mind": _move("calm-mind", "Calm Mind", "psychic", Category.STATUS, pp=20, effect="boost", target="self", stat_changes=(("spa", 1), ("spd", 1))),
    "dragon-dance": _move("dragon-dance", "Dragon Dance", "dragon", Category.STATUS, pp=20, effect="boost", target="self", stat_changes=(("atk", 1), ("spe", 1))),
    "recover": _move("recover", "Recover", "normal", Category.STATUS, pp=5, effect="heal", target="self"),
    "roost": _move("roost", "Roost", "flying", Category.STATUS, pp=5, effect="heal", target="self"),
    "synthesis": _move("synthesis", "Synthesis", "grass", Category.STATUS, pp=5, effect="heal", target="self"),
    "rest": _move("rest", "Rest", "psychic", Category.STATUS, pp=5, effect="rest", target="self"),
    "protect": _move("protect", "Protect", "normal", Category.STATUS, pp=10, priority=4, effect="protect", target="self"),
    "reflect": _move("reflect", "Reflect", "psychic", Category.STATUS, pp=20, effect="screen_reflect", target="self"),
    "light-screen": _move("light-screen", "Light Screen", "psychic", Category.STATUS, pp=30, effect="screen_light", target="self"),
    "defog": _move("defog", "Defog", "flying", Category.STATUS, pp=15, effect="defog"),
    "will-o-wisp": _move("will-o-wisp", "Will-O-Wisp", "fire", Category.STATUS, pp=15, accuracy=85, effect="status", status=Status.BURN),
    "thunder-wave": _move("thunder-wave", "Thunder Wave", "electric", Category.STATUS, pp=20, accuracy=90, effect="status", status=Status.PARALYSIS),
    "toxic": _move("toxic", "Toxic", "poison", Category.STATUS, pp=10, accuracy=90, effect="status", status=Status.TOXIC),
    "sleep-powder": _move("sleep-powder", "Sleep Powder", "grass", Category.STATUS, pp=15, accuracy=75, effect="sleep", status=Status.SLEEP),
    "stealth-rock": _move("stealth-rock", "Stealth Rock", "rock", Category.STATUS, pp=20, effect="hazard"),
    "rapid-spin": _move("rapid-spin", "Rapid Spin", "normal", Category.PHYSICAL, 50, pp=40, effect="rapid_spin"),
}

ITEMS: dict[str, Item] = {
    "leftovers": Item("leftovers", "Leftovers", "leftovers"),
    "life-orb": Item("life-orb", "Life Orb", "life_orb"),
    "heavy-duty-boots": Item("heavy-duty-boots", "Heavy-Duty Boots", "boots"),
    "charizardite-x": Item("charizardite-x", "Charizardite X", "mega_stone"),
    "charizardite-y": Item("charizardite-y", "Charizardite Y", "mega_stone"),
    "mewtwonite-x": Item("mewtwonite-x", "Mewtwonite X", "mega_stone"),
    "mewtwonite-y": Item("mewtwonite-y", "Mewtwonite Y", "mega_stone"),
    "normalium-z": Item("normalium-z", "Normalium Z", "z_crystal"),
    "z-crystal": Item("z-crystal", "Sandbox Z-Crystal", "z_crystal"),
}

NATURES: dict[str, Nature] = {
    "Hardy": Nature("Hardy"), "Adamant": Nature("Adamant", "atk", "spa"),
    "Modest": Nature("Modest", "spa", "atk"), "Jolly": Nature("Jolly", "spe", "spa"),
    "Timid": Nature("Timid", "spe", "atk"), "Bold": Nature("Bold", "def", "atk"),
    "Calm": Nature("Calm", "spd", "atk"), "Impish": Nature("Impish", "def", "spa"),
    "Careful": Nature("Careful", "spd", "spa"), "Quiet": Nature("Quiet", "spa", "spe"),
}

def load_species() -> dict[str, Species]:
    raw = json.loads((DATA / "gen1_species.json").read_text(encoding="utf-8"))["species"]
    # Runtime validation keeps malformed hand-edited/imported JSON from reaching battle code.
    records = [SpeciesRecord.model_validate(entry) for entry in raw]
    if len(records) != 151 or {record.dex for record in records} != set(range(1, 152)):
        raise ValueError("The Gen I roster file must contain exactly one canonical entry for each dex ID 1–151.")
    return {record.slug: Species(record.dex, record.name, tuple(record.types), record.base_stats, tuple(record.abilities), record.hidden_ability) for record in records}

SPECIES = load_species()
# Full sourced catalog/learnsets support data browsing and legality tooling. Only MOVES is
# executable today; retaining this distinction avoids pretending every catalog effect works.
MOVE_CATALOG = json.loads((DATA / "moves_catalog.json").read_text(encoding="utf-8"))["moves"]
LEARNSETS: dict[str, list[str]] = json.loads((DATA / "gen1_learnsets.json").read_text(encoding="utf-8"))["learnsets"]

def learnable_moves(slug: str, *, executable_only: bool = True) -> list[str]:
    species = SPECIES[slug]
    moves = LEARNSETS.get(str(species.dex), [])
    return [move_id for move_id in moves if (move_id in MOVES or not executable_only)]

def make_pokemon(slug: str, move_ids: list[str], *, level: int = 50, nature: str = "Hardy", ability: str | None = None, item: str | None = "leftovers", nickname: str | None = None) -> Pokemon:
    species = SPECIES[slug]
    ability = ability or (species.abilities[0] if species.abilities else None)
    slots = [MoveSlot(mid, MOVES[mid].pp, MOVES[mid].pp) for mid in move_ids]
    mon = Pokemon(species=species, nickname=nickname, level=level, nature=NATURES[nature], ability=ability, item=ITEMS.get(item) if item else None, moves=slots)
    # Current HP is set here rather than deferring it to UI code.
    from .stats import base_stat
    mon.current_hp = base_stat(mon, "hp")
    return mon

"""Configurable battle phenomena.

Each activation is explicit in a MoveAction and routed through BattleState, so GUI and AI
share one legality path. The module contains only the forms and effects currently tested.
"""
from __future__ import annotations
from dataclasses import replace
from .models import Category, Move, Pokemon, Species
from .stats import base_stat, max_hp

MEGA_FORMS: dict[tuple[str, str], Species] = {
    ("charizard", "charizardite-x"): Species(6, "Mega Charizard X", ("fire", "dragon"), {"hp":78,"atk":130,"def":111,"spa":130,"spd":85,"spe":100}, ("tough-claws",)),
    ("charizard", "charizardite-y"): Species(6, "Mega Charizard Y", ("fire", "flying"), {"hp":78,"atk":104,"def":78,"spa":159,"spd":115,"spe":100}, ("drought",)),
    ("mewtwo", "mewtwonite-x"): Species(150, "Mega Mewtwo X", ("psychic", "fighting"), {"hp":106,"atk":190,"def":100,"spa":154,"spd":100,"spe":130}, ("steadfast",)),
    ("mewtwo", "mewtwonite-y"): Species(150, "Mega Mewtwo Y", ("psychic",), {"hp":106,"atk":150,"def":70,"spa":194,"spd":120,"spe":140}, ("insomnia",)),
}
GMAX_SPECIES = {"charizard", "butterfree", "pikachu", "meowth", "machamp", "gengar", "kingler", "lapras", "eevee", "snorlax", "garbodor", "melmetal"}
TYPE_NAMES = {"normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy", "stellar"}

# Official Z power bands for ordinary damaging moves; move-specific exceptions are not yet modeled.
def z_power(power: int) -> int:
    if power <= 55: return 100
    if power <= 65: return 120
    if power <= 75: return 140
    if power <= 85: return 160
    if power <= 95: return 175
    if power <= 100: return 180
    if power <= 110: return 185
    if power <= 125: return 190
    if power <= 130: return 195
    return 200

def max_power(power: int, move_type: str) -> int:
    # Standard generic Max Move band. Fighting/Poison exceptions and special moves are later data work.
    if power <= 40: return 90
    if power <= 50: return 100
    if power <= 60: return 110
    if power <= 70: return 120
    if power <= 100: return 130
    if power <= 140: return 140
    return 150

def activated_move(move: Move, phenomenon: str | None, mon: Pokemon) -> Move:
    if phenomenon == "z":
        return replace(move, id=f"z-{move.id}", name=f"{move.name} — Z", power=z_power(move.power), accuracy=None, effect="z_move", effect_chance=0, drain_fraction=0.0, recoil_fraction=0.0)
    if phenomenon in {"dynamax", "gigantamax"}:
        labels = {"fire":"Max Flare", "water":"Max Geyser", "grass":"Max Overgrowth", "electric":"Max Lightning", "flying":"Max Airstream", "rock":"Max Rockfall", "ground":"Max Quake", "steel":"Max Steelspike", "fighting":"Max Knuckle", "poison":"Max Ooze", "psychic":"Max Mindstorm", "ghost":"Max Phantasm", "dark":"Max Darkness", "dragon":"Max Wyrmwind", "ice":"Max Hailstorm"}
        return replace(move, id=f"max-{move.id}", name=labels.get(move.type, "Max Strike"), power=max_power(move.power, move.type), accuracy=None, effect="max_move", effect_chance=0, drain_fraction=0.0, recoil_fraction=0.0)
    return move

def can_activate(mon: Pokemon, phenomenon: str, rules, used: set[str]) -> tuple[bool, str]:
    if phenomenon == "mega":
        if not rules.allow_mega: return False, "Mega Evolution is disabled by this ruleset."
        if "mega" in used: return False, "Mega Evolution has already been used by this side."
        item_id = mon.item.id if mon.item else ""
        original = mon.species.name.lower().replace("mega ", "")
        if (original, item_id) not in MEGA_FORMS: return False, "This Pokémon is not holding its compatible Mega Stone."
        return True, ""
    if phenomenon == "z":
        if not rules.allow_z_moves: return False, "Z-Moves are disabled by this ruleset."
        if "z" in used: return False, "A Z-Move has already been used by this side."
        if not mon.item or not mon.item.id.endswith("-z"): return False, "This Pokémon needs a compatible Z-Crystal."
        return True, ""
    if phenomenon in {"dynamax", "gigantamax"}:
        if not rules.allow_dynamax: return False, "Dynamax is disabled by this ruleset."
        if "dynamax" in used or mon.volatile.get("dynamax_turns", 0): return False, "Dynamax has already been used by this side."
        if phenomenon == "gigantamax" and mon.species.name.lower().replace("mega ", "") not in GMAX_SPECIES: return False, "This species has no implemented Gigantamax form."
        return True, ""
    if phenomenon == "tera":
        if not rules.allow_tera: return False, "Terastallization is disabled by this ruleset."
        if "tera" in used: return False, "Terastallization has already been used by this side."
        tera_type = mon.volatile.get("tera_type", mon.species.types[0])
        if tera_type not in TYPE_NAMES: return False, "Invalid Tera Type."
        return True, ""
    return False, f"Unknown battle phenomenon: {phenomenon}"

def activate(mon: Pokemon, phenomenon: str, rules) -> str:
    """Mutate only battle state and return its player-facing activation message."""
    if phenomenon == "mega":
        original = mon.species.name.lower().replace("mega ", "")
        form = MEGA_FORMS[(original, mon.item.id)]
        ratio = (mon.current_hp or 0) / max(1, max_hp(mon))
        mon.species = form; mon.ability = form.abilities[0]; mon.revealed_ability = True
        mon.current_hp = max(1, int(base_stat(mon, "hp") * ratio))
        mon.volatile["mega"] = True
        return f"{mon.label} Mega Evolved into {form.name}!"
    if phenomenon in {"dynamax", "gigantamax"}:
        mon.current_hp = (mon.current_hp or 0) * 2
        mon.volatile["dynamax_turns"] = rules.dynamax_turns
        mon.volatile["gigantamax"] = phenomenon == "gigantamax"
        return f"{mon.label} {('Gigantamaxed' if phenomenon == 'gigantamax' else 'Dynamaxed')}!"
    if phenomenon == "tera":
        tera_type = mon.volatile.get("tera_type", mon.species.types[0])
        mon.volatile["tera_active"] = True
        return f"{mon.label} Terastallized into the {tera_type.title()} type!"
    if phenomenon == "z":
        return f"{mon.label} surrounded itself with Z-Power!"
    raise ValueError(phenomenon)

def end_of_turn(mon: Pokemon) -> str | None:
    turns = mon.volatile.get("dynamax_turns", 0)
    if not turns: return None
    turns -= 1; mon.volatile["dynamax_turns"] = turns
    if turns == 0:
        # Preserve HP ratio as the doubled max HP collapses.
        mon.current_hp = min(base_stat(mon, "hp"), ((mon.current_hp or 0) + 1) // 2)
        mon.volatile.pop("gigantamax", None)
        return f"{mon.label} returned to normal size!"
    return None

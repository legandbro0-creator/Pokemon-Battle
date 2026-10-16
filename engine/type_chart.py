"""Modern 18-type chart used by the default cross-generation sandbox ruleset."""
from __future__ import annotations

# Each entry lists defending types that receive double damage. Immunities are handled explicitly.
SUPER: dict[str, set[str]] = {
    "normal": set(), "fire": {"grass", "ice", "bug", "steel"},
    "water": {"fire", "ground", "rock"}, "electric": {"water", "flying"},
    "grass": {"water", "ground", "rock"}, "ice": {"grass", "ground", "flying", "dragon"},
    "fighting": {"normal", "ice", "rock", "dark", "steel"}, "poison": {"grass", "fairy"},
    "ground": {"fire", "electric", "poison", "rock", "steel"}, "flying": {"grass", "fighting", "bug"},
    "psychic": {"fighting", "poison"}, "bug": {"grass", "psychic", "dark"},
    "rock": {"fire", "ice", "flying", "bug"}, "ghost": {"psychic", "ghost"},
    "dragon": {"dragon"}, "dark": {"psychic", "ghost"}, "steel": {"ice", "rock", "fairy"},
    "fairy": {"fighting", "dragon", "dark"},
}
RESIST: dict[str, set[str]] = {
    "normal": {"rock", "steel"}, "fire": {"fire", "water", "rock", "dragon"},
    "water": {"water", "grass", "dragon"}, "electric": {"electric", "grass", "dragon"},
    "grass": {"fire", "grass", "poison", "flying", "bug", "dragon", "steel"},
    "ice": {"fire", "water", "ice", "steel"}, "fighting": {"poison", "flying", "psychic", "bug", "fairy"},
    "poison": {"poison", "ground", "rock", "ghost"}, "ground": {"grass", "bug"},
    "flying": {"electric", "rock", "steel"}, "psychic": {"psychic", "steel"},
    "bug": {"fire", "fighting", "poison", "flying", "ghost", "steel", "fairy"},
    "rock": {"fighting", "ground", "steel"}, "ghost": {"dark"}, "dragon": {"steel", "fairy"},
    "dark": {"fighting", "dark", "fairy"}, "steel": {"fire", "water", "electric", "steel"},
    "fairy": {"fire", "poison", "steel"},
}
IMMUNE: dict[str, set[str]] = {
    "normal": {"ghost"}, "electric": {"ground"}, "fighting": {"ghost"}, "poison": {"steel"},
    "ground": {"flying"}, "psychic": {"dark"}, "ghost": {"normal"}, "dragon": {"fairy"},
}

def effectiveness(attacking: str, defending: tuple[str, ...] | list[str]) -> float:
    """Return exact type multiplier for one attacking type against all defender types."""
    attacking = attacking.lower()
    multiplier = 1.0
    for defender in defending:
        defender = defender.lower()
        if defender in IMMUNE.get(attacking, set()):
            return 0.0
        if defender in SUPER.get(attacking, set()):
            multiplier *= 2
        elif defender in RESIST.get(attacking, set()):
            multiplier *= 0.5
    return multiplier

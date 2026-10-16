"""Single source of truth for damage estimates and rolled move damage."""
from __future__ import annotations
from dataclasses import dataclass
from .models import Category, Move, Pokemon, Status
from .stats import effective_stat, effective_types
from .type_chart import effectiveness

@dataclass(frozen=True, slots=True)
class DamageResult:
    minimum: int
    maximum: int
    expected: float
    type_multiplier: float
    stab: float
    critical: bool


def type_multiplier(move: Move, attacker: Pokemon, defender: Pokemon) -> float:
    """Account for type immunity and the implemented Levitate ability."""
    if move.type == "ground" and defender.ability == "levitate":
        return 0.0
    return effectiveness(move.type, effective_types(defender))

def estimate_damage(attacker: Pokemon, defender: Pokemon, move: Move, *, critical: bool = False, weather: str | None = None, terrain: str | None = None, screen: float = 1.0) -> DamageResult:
    if move.category == Category.STATUS or move.power <= 0:
        return DamageResult(0, 0, 0.0, 1.0, 1.0, critical)
    offense = effective_stat(attacker, "atk" if move.category == Category.PHYSICAL else "spa")
    defense = effective_stat(defender, "def" if move.category == Category.PHYSICAL else "spd")
    # Core main-series formula, with all intermediate divisions floored.
    base = (((2 * attacker.level // 5 + 2) * move.power * offense // max(1, defense)) // 50) + 2
    original_types = attacker.species.types
    if attacker.volatile.get("tera_active") and attacker.volatile.get("tera_type") == move.type:
        stab = 2.0 if move.type in original_types else 1.5
    else:
        stab = 1.5 if move.type in original_types else 1.0
    type_mult = type_multiplier(move, attacker, defender)
    crit = 1.5 if critical else 1.0
    burn = 0.5 if move.category == Category.PHYSICAL and attacker.status == Status.BURN and attacker.ability != "guts" else 1.0
    item = 1.3 if attacker.item and attacker.item.effect == "life_orb" else 1.0
    weather_mod = 1.0
    if weather == "sun": weather_mod = 1.5 if move.type == "fire" else (0.5 if move.type == "water" else 1.0)
    elif weather == "rain": weather_mod = 1.5 if move.type == "water" else (0.5 if move.type == "fire" else 1.0)
    terrain_mod = 1.0
    grounded = "flying" not in effective_types(attacker) and attacker.ability != "levitate"
    if grounded and ((terrain == "electric" and move.type == "electric") or (terrain == "grassy" and move.type == "grass") or (terrain == "psychic" and move.type == "psychic")):
        terrain_mod = 1.3
    if terrain == "misty" and move.type == "dragon": terrain_mod *= 0.5
    if terrain == "grassy" and move.id.endswith("earthquake"): terrain_mod *= 0.5
    modifier = stab * type_mult * crit * burn * item * weather_mod * terrain_mod * (1.0 if critical else screen)
    if type_mult == 0:
        return DamageResult(0, 0, 0.0, type_mult, stab, critical)
    # Official random range is [85, 100] percentage inclusive; normal damage cannot be < 1.
    minimum = max(1, int(base * modifier * 0.85))
    maximum = max(1, int(base * modifier))
    return DamageResult(minimum, maximum, (minimum + maximum) / 2, type_mult, stab, critical)

def rolled_damage(attacker: Pokemon, defender: Pokemon, move: Move, rng, *, critical: bool = False, random_damage: bool = True, weather: str | None = None, terrain: str | None = None, screen: float = 1.0) -> tuple[int, DamageResult]:
    estimate = estimate_damage(attacker, defender, move, critical=critical, weather=weather, terrain=terrain, screen=screen)
    if estimate.maximum == 0:
        return 0, estimate
    if not random_damage:
        return estimate.maximum, estimate
    roll = rng.randint(85, 100)
    # Recompute using min/max interpolation does not create illegal 16 rolls for all values;
    # it still preserves the same formula bounds used by this engine.
    damage = max(1, int(estimate.maximum * roll / 100))
    return damage, estimate

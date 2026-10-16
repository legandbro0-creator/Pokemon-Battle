from __future__ import annotations
from .models import Pokemon

def base_stat(mon: Pokemon, stat: str) -> int:
    base = mon.species.base_stats[stat]
    iv = mon.ivs.get(stat, 31)
    ev = mon.evs.get(stat, 0)
    if stat == "hp":
        return ((2 * base + iv + ev // 4) * mon.level) // 100 + mon.level + 10
    raw = ((2 * base + iv + ev // 4) * mon.level) // 100 + 5
    if mon.nature.increase == stat:
        raw = (raw * 110) // 100
    elif mon.nature.decrease == stat:
        raw = (raw * 90) // 100
    return raw

def max_hp(mon: Pokemon) -> int:
    """Battle maximum HP including the temporary Dynamax multiplier when active."""
    multiplier = 2 if mon.volatile.get("dynamax_turns", 0) > 0 else 1
    return base_stat(mon, "hp") * multiplier

def effective_types(mon: Pokemon) -> tuple[str, ...]:
    """Battle types after Terastallization; Stellar preserves defensive typing."""
    tera_type = mon.volatile.get("tera_type")
    if mon.volatile.get("tera_active") and tera_type and tera_type != "stellar":
        return (tera_type,)
    return mon.species.types

def all_stats(mon: Pokemon) -> dict[str, int]:
    stats = {stat: base_stat(mon, stat) for stat in ("hp", "atk", "def", "spa", "spd", "spe")}
    stats["hp"] = max_hp(mon)
    return stats

def stage_multiplier(stage: int) -> tuple[int, int]:
    stage = max(-6, min(6, stage))
    return (2 + stage, 2) if stage >= 0 else (2, 2 - stage)

def effective_stat(mon: Pokemon, stat: str) -> int:
    value = base_stat(mon, stat)
    numerator, denominator = stage_multiplier(mon.stages.get(stat, 0))
    value = max(1, value * numerator // denominator)
    if stat == "spe" and mon.status.value == "par":
        value = max(1, value // 2)
    return value

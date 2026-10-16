from __future__ import annotations
from .models import Pokemon, Team
from .stats import all_stats

def pokemon_summary(mon: Pokemon, *, include_private: bool = True) -> dict:
    data = {
        "species": mon.species.name, "dex": mon.species.dex, "nickname": mon.nickname,
        "level": mon.level, "types": list(mon.species.types), "ability": mon.ability,
        "item": mon.item.name if mon.item else None, "moves": [slot.move_id for slot in mon.moves],
        "nature": mon.nature.name, "ivs": dict(mon.ivs), "evs": dict(mon.evs), "stats": all_stats(mon),
    }
    if not include_private:
        data.pop("item"); data.pop("moves"); data.pop("ivs"); data.pop("evs")
    return data

def team_summary(team: Team, *, include_private: bool = True) -> dict:
    return {"name": team.name, "pokemon": [pokemon_summary(mon, include_private=include_private) for mon in team.pokemon]}

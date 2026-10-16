"""Versioned offline team import/export plus battle-legality validation."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from .content import ITEMS, MOVES, NATURES, SPECIES, make_pokemon
from .models import BattleRules, Pokemon, Status, Team
from .stats import base_stat

TEAM_SCHEMA_VERSION = 1

@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: str  # error / warning
    code: str
    message: str
    slot: int | None = None


def pokemon_to_dict(mon: Pokemon) -> dict:
    return {
        "species": next(slug for slug, species in SPECIES.items() if species.dex == mon.species.dex and species.name == mon.species.name),
        "nickname": mon.nickname, "level": mon.level, "nature": mon.nature.name,
        "ability": mon.ability, "item": mon.item.id if mon.item else None,
        "ivs": mon.ivs, "evs": mon.evs, "moves": [slot.move_id for slot in mon.moves],
        "current_hp": mon.current_hp, "status": mon.status.value,
        "tera_type": mon.volatile.get("tera_type"),
    }


def pokemon_from_dict(data: dict) -> Pokemon:
    required = {"species", "moves"}
    missing = required - set(data)
    if missing: raise ValueError(f"Pokémon record missing required field(s): {', '.join(sorted(missing))}")
    slug = data["species"]
    if slug not in SPECIES: raise ValueError(f"Unknown species slug: {slug}")
    move_ids = data["moves"]
    unknown = [move_id for move_id in move_ids if move_id not in MOVES]
    if unknown: raise ValueError(f"This playable build does not execute move(s): {', '.join(unknown)}")
    nature = data.get("nature", "Hardy")
    if nature not in NATURES: raise ValueError(f"Unknown nature: {nature}")
    item = data.get("item")
    if item and item not in ITEMS: raise ValueError(f"Unknown implemented item: {item}")
    mon = make_pokemon(slug, move_ids, level=int(data.get("level", 50)), nature=nature,
                       ability=data.get("ability"), item=item, nickname=data.get("nickname"))
    mon.ivs.update({str(k): int(v) for k, v in data.get("ivs", {}).items()})
    mon.evs.update({str(k): int(v) for k, v in data.get("evs", {}).items()})
    mon.current_hp = min(base_stat(mon, "hp"), max(0, int(data.get("current_hp", base_stat(mon, "hp")))))
    mon.status = Status(data.get("status", ""))
    if data.get("tera_type"): mon.volatile["tera_type"] = data["tera_type"]
    return mon


def team_to_dict(team: Team) -> dict:
    return {"schema_version": TEAM_SCHEMA_VERSION, "name": team.name, "pokemon": [pokemon_to_dict(mon) for mon in team.pokemon]}


def team_from_dict(data: dict) -> Team:
    if data.get("schema_version") != TEAM_SCHEMA_VERSION:
        raise ValueError(f"Unsupported team schema version: {data.get('schema_version')}")
    pokemon = [pokemon_from_dict(record) for record in data.get("pokemon", [])]
    return Team(str(data.get("name", "Imported Team")), pokemon)


def save_team(team: Team, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(team_to_dict(team), indent=2) + "\n", encoding="utf8")


def load_team(path: str | Path) -> Team:
    return team_from_dict(json.loads(Path(path).read_text(encoding="utf8")))


def validate_team(team: Team, rules: BattleRules, *, sandbox: bool = False) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if len(team.pokemon) != rules.team_size:
        issues.append(ValidationIssue("error", "team-size", f"Team must contain exactly {rules.team_size} Pokémon; found {len(team.pokemon)}."))
    species_seen: set[int] = set(); items_seen: set[str] = set()
    for index, mon in enumerate(team.pokemon):
        if not (1 <= mon.level <= rules.level_cap):
            issues.append(ValidationIssue("error", "level", f"{mon.label} level must be 1–{rules.level_cap}.", index))
        if len(mon.moves) != 4:
            issues.append(ValidationIssue("error", "move-count", f"{mon.label} must have four configured move slots.", index))
        for name, value in mon.ivs.items():
            if not 0 <= value <= 31: issues.append(ValidationIssue("error", "iv", f"{mon.label} has illegal {name} IV {value}.", index))
        ev_total = sum(mon.evs.values())
        if any(value < 0 or value > rules.ev_cap_per_stat for value in mon.evs.values()) or ev_total > rules.ev_cap_total:
            issues.append(ValidationIssue("error", "ev", f"{mon.label} has an illegal EV distribution ({ev_total} total).", index))
        if rules.species_clause and mon.species.dex in species_seen:
            issues.append(ValidationIssue("error", "species-clause", f"Species Clause forbids duplicate {mon.species.name}.", index))
        species_seen.add(mon.species.dex)
        if mon.item and mon.item.id in items_seen:
            issues.append(ValidationIssue("warning", "item-clause", f"Duplicate item {mon.item.name}.", index))
        if mon.item: items_seen.add(mon.item.id)
        unsupported = [slot.move_id for slot in mon.moves if slot.move_id not in MOVES]
        if unsupported and not sandbox:
            issues.append(ValidationIssue("error", "move-unsupported", f"Unsupported executable move(s): {', '.join(unsupported)}.", index))
    return issues

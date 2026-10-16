"""Ruleset presets and versioned JSON persistence."""
from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
from .models import BattleRules

PRESETS: dict[str, BattleRules] = {
    "competitive": BattleRules(name="Modern Competitive Singles", species_clause=True),
    "gen3-inspired": BattleRules(name="Generation III-inspired Singles", species_clause=True, allow_mega=False, allow_z_moves=False, allow_dynamax=False, allow_tera=False),
    "mega": BattleRules(name="Mega Evolution Singles", species_clause=True, allow_mega=True),
    "z-moves": BattleRules(name="Z-Move Singles", species_clause=True, allow_z_moves=True),
    "dynamax": BattleRules(name="Dynamax Singles", species_clause=True, allow_dynamax=True),
    "tera": BattleRules(name="Terastallization Singles", species_clause=True, allow_tera=True),
    "national-dex-sandbox": BattleRules(name="National Dex Sandbox", allow_mega=True, allow_z_moves=True, allow_dynamax=True, allow_tera=True),
}

def save_ruleset(rules: BattleRules, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"schema_version": 1, **asdict(rules)}, indent=2) + "\n", encoding="utf8")

def load_ruleset(path: str | Path) -> BattleRules:
    data = json.loads(Path(path).read_text(encoding="utf8")); data.pop("schema_version", None)
    return BattleRules(**data)

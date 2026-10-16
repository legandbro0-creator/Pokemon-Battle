"""Build offline structured move catalog + all Gen-I species learnset index.

This importer preserves sourced move metadata even when an effect is not yet executable by
`engine.content.MOVES`; the validator blocks such moves in non-sandbox playable battles.
"""
from __future__ import annotations
import csv, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def read(name: str):
    with (DATA / name).open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(f))

def integer(value: str) -> int | None:
    return int(value) if value not in ("", None) else None

def main() -> None:
    type_names = {int(row["id"]): row["identifier"] for row in read("types.csv")}
    damage_classes = {int(row["id"]): row["identifier"] for row in read("move_damage_classes.csv")}
    targets = {int(row["id"]): row["identifier"] for row in read("move_targets.csv")}
    english_effects: dict[int, str] = {}
    for row in read("move_effect_prose.csv"):
        if row["local_language_id"] == "9":  # English
            english_effects[int(row["move_effect_id"])] = row["short_effect"]
    catalog = []
    for row in read("moves.csv"):
        catalog.append({
            "id": int(row["id"]), "slug": row["identifier"], "generation": int(row["generation_id"]),
            "type": type_names[int(row["type_id"])], "power": integer(row["power"]),
            "pp": integer(row["pp"]), "accuracy": integer(row["accuracy"]), "priority": int(row["priority"]),
            "target": targets[int(row["target_id"])], "category": damage_classes[int(row["damage_class_id"])],
            "effect_id": integer(row["effect_id"]) or 0, "effect_chance": integer(row["effect_chance"]),
            "effect_summary": english_effects.get(integer(row["effect_id"]) or 0, ""),
        })
    # All sourced moves available to each Gen-I species in any recorded PokeAPI version/method.
    learnsets: dict[int, set[int]] = defaultdict(set)
    for row in read("pokemon_moves.csv"):
        dex = int(row["pokemon_id"])
        if 1 <= dex <= 151: learnsets[dex].add(int(row["move_id"]))
    by_id = {move["id"]: move["slug"] for move in catalog}
    output = {str(dex): sorted(by_id[mid] for mid in move_ids if mid in by_id) for dex, move_ids in sorted(learnsets.items())}
    if len(output) != 151:
        raise RuntimeError(f"Expected 151 learnsets; got {len(output)}")
    (DATA / "moves_catalog.json").write_text(json.dumps({"schema_version": 1, "source": "PokeAPI CSV snapshot", "moves": catalog}, indent=2) + "\n", encoding="utf8")
    (DATA / "gen1_learnsets.json").write_text(json.dumps({"schema_version": 1, "source": "PokeAPI CSV snapshot", "learnsets": output}, indent=2) + "\n", encoding="utf8")
    print(f"Wrote {len(catalog)} move records and {len(output)} Gen-I learnsets")

if __name__ == "__main__": main()

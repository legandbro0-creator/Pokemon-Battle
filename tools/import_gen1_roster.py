"""Create the offline, structured Gen I roster from vendored PokeAPI CSV source files.

Run after refreshing source CSVs. It intentionally filters to national dex IDs 1-151 and
stores only canonical default forms. The output is consumed at runtime without network.
"""
from __future__ import annotations
import csv, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def rows(name: str):
    with (DATA / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))

def main() -> None:
    names = {int(r['id']): r['identifier'] for r in rows('pokemon.csv')
             if int(r['id']) <= 151 and r['is_default'] == '1'}
    type_names = {int(r['id']): r['identifier'] for r in rows('types.csv')}
    ability_names = {int(r['id']): r['identifier'] for r in rows('abilities.csv')}
    stats: dict[int, dict[str, int]] = defaultdict(dict)
    stat_keys = {1: 'hp', 2: 'atk', 3: 'def', 4: 'spa', 5: 'spd', 6: 'spe'}
    for r in rows('pokemon_stats.csv'):
        pid, stat = int(r['pokemon_id']), int(r['stat_id'])
        if pid in names and stat in stat_keys:
            stats[pid][stat_keys[stat]] = int(r['base_stat'])
    types: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for r in rows('pokemon_types.csv'):
        pid = int(r['pokemon_id'])
        if pid in names:
            types[pid].append((int(r['slot']), type_names[int(r['type_id'])]))
    abilities: dict[int, list[tuple[int, bool, str]]] = defaultdict(list)
    for r in rows('pokemon_abilities.csv'):
        pid = int(r['pokemon_id'])
        if pid in names:
            abilities[pid].append((int(r['slot']), r['is_hidden'] == '1', ability_names[int(r['ability_id'])]))
    output = []
    for dex, name in sorted(names.items()):
        abs_ = sorted(abilities[dex])
        output.append({
            'dex': dex,
            'name': name.replace('-', ' ').title(),
            'slug': name,
            'types': [name for _, name in sorted(types[dex])],
            'base_stats': stats[dex],
            'abilities': [name for _, hidden, name in abs_ if not hidden],
            'hidden_ability': next((name for _, hidden, name in abs_ if hidden), None),
        })
    if len(output) != 151:
        raise RuntimeError(f'Expected all 151 canonical Gen I species, got {len(output)}')
    target = DATA / 'gen1_species.json'
    target.write_text(json.dumps({'schema_version': 1, 'source': 'PokeAPI CSV snapshot', 'species': output}, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {target}: {len(output)} species')

if __name__ == '__main__':
    main()

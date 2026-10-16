# Pokémon — Tactical Battle Simulator

> A fan-made offline tactical battle simulator inspired by competitive Pokémon battles. It is not affiliated with or endorsed by The Pokémon Company, Nintendo, or Game Freak.

## Run locally

```bash
cd pokemon_battler
# 1. Unzip the sprite packs (one time) — see "Assets" below
cd assets && unzip Pokemon.zip && unzip items.zip && cd ..
# 2. Install dependencies and start
python -m pip install -r requirements.txt
python main.py
```

The game scales its 1280×760 interface to fit the window, so it also fits small screens.

### Termux (Android) + Termux:X11

`pygame-ce` cannot be built on Android, so install the original `pygame` instead of using `requirements.txt`:

```bash
pkg install x11-repo
pkg install python clang make pkg-config sdl2 sdl2-image sdl2-mixer sdl2-ttf freetype libpng libjpeg-turbo portmidi unzip
pip install pygame
termux-x11 :0 &
export DISPLAY=:0
python main.py
```

No other third-party packages are needed (`pytest` is optional, for the tests).

Tests (from the repository root):

```bash
PYTHONPATH=pokemon_battler python -m pytest pokemon_battler/tests -q
```

No game-time internet connection is used. The Pygame presentation now uses Generation III (FireRed/LeafGreen) sprites for all 151 species — front sprites for the foe, back sprites for the player, small icons in the roster, team builder, switch buttons and menu — plus item icons for held items, the party Poké Ball strip and the Mega/Z buttons. If a sprite file is ever missing, the UI falls back to the old abstract marker instead of crashing.

### Assets

All sprites and icons ship as two zip files in `assets/`. **Unzip both inside `assets/` before running the game** (the game reads the extracted PNGs, not the zips):

```text
assets/
├── Pokemon.zip   →  extracts to  pokemon/front/<dex>.png   (151 front sprites, 64×64 RGBA)
│                                 pokemon/back/<dex>.png    (151 back sprites, 64×64 RGBA)
└── items.zip     →  extracts to  items/<item-id>.png       (650 item icons, 30×30 RGBA)
```

```bash
cd assets
unzip Pokemon.zip
unzip items.zip
```

After extracting, the folder should look like `assets/pokemon/front/1.png` … `assets/pokemon/back/151.png` and `assets/items/leftovers.png`.

- Pokémon files are named by National Dex number (Bulbasaur = `1.png`, Mew = `151.png`) and come from the Generation III FireRed/LeafGreen sprite set.
- Item icon filenames match the ids in `engine/content.py` (`ITEMS`), so a new item only needs a PNG with its id. 647 icons come from the supplied item pack; `heavy-duty-boots`, `normalium-z` and `z-crystal` had no sprite in the pack and are generated icons.
- If a file is missing (for example the zips were not extracted), the UI falls back to the old abstract marker instead of crashing.
- Pokémon artwork is © Nintendo / Creatures Inc. / Game Freak; it is included for personal, non-commercial fan use only and should not be redistributed commercially.

## Current playable build

The application launches into a desktop menu with **Play Tactical Battle**, **Team Builder**, **Battle Rules & AI**, **Gen I Roster**, and **Battle History** screens.

### Completed, runnable foundations

- **6v6 battle to victory/defeat:** legal actions, priority/speed ordering, switching, forced player replacement, fainting, residual effects and seeded random outcomes.
- **151-species offline Gen I roster:** dex, modern type(s), base stats, regular/hidden ability data; record validation rejects malformed roster data.
- **Full sourced data browser:** 937 structured move metadata records and a sourced learnset index for each of the 151 species. A move is never treated as battle-executable merely because it appears in the catalog.
- **Team builder/editor:** six editable slots, 151-species browser, ability/item cycling, EV preset, Tera-type selection, executable learned move selection, validation, and local JSON save/load at `teams/user_team.json`.
- **Rules and resources:** selectable competitive/sandbox presets, species clause, mixed-phenomenon setting, Mega, Z-Move, Dynamax/Gigantamax, and Terastallization toggles.
- **Implemented battle phenomena subset:** compatible Mega Charizard X/Y and Mega Mewtwo X/Y; generic damaging Z-Moves; generic Dynamax plus eligible Gen-I Gigantamax labels; Tera defensive typing and STAB. These are ruleset-gated and use the same action validation path as normal moves.
- **Implemented field subset:** Stealth Rock, Rapid Spin, Defog, Reflect, Light Screen, sand/hail chip, sun/rain damage modifiers, terrain damage/status/priority/recovery interactions, and generic Max Move field/stat effects.
- **Fair tactical AI:** legal-action generation, public-information projection, damage/KO estimation, switch/recovery/status/hazard scoring, optional resource use, and a bounded probabilistic counterplay layer. Its rationale shown in the UI originates from the actual scored action.
- **Analysis/history:** `A` toggles an analysis panel; completed battles save deterministic replay JSON under `replays/` and appear in the session history.

### Controls

- Click an action or switch button in battle.
- On a forced replacement, click a living teammate.
- Click a listed phenomenon, then a damaging move, to activate it when the active ruleset allows it.
- Press `A` in battle for analysis; press `Esc` to return to the menu.
- In roster/team-builder views use left/right arrows to change the species page.

## Architecture

```text
engine/        authoritative, UI-independent models / state machine / damage / rules
ai/            fair-information controller, opponent model, bounded predictive evaluator
gui/           Pygame desktop presentation and interaction only
assets/        Pokemon.zip and items.zip (sprites and item icons; unzip before running)
data/          normalized offline roster/catalog/learnset data
tools/         reproducible PokeAPI CSV import scripts
teams/         user team JSONs
replays/       deterministic battle records
tests/         mechanics, data, persistence, AI and full-battle regression tests
```

`BattleState` is the sole authority for the turn flow:

```text
validate actions → determine order → execute actions → resolve fainting
→ replacements → residual / field effects → end temporary forms → end battle
```

The GUI and AI do not duplicate damage calculations. The AI only receives its own full team state and a public projection of the player in normal `fair` information mode. It never reads unrevealed player moves, item, ability, nature, IVs, or EVs.

## Data provenance and licensing notes

`gen1_species.json`, `moves_catalog.json`, and `gen1_learnsets.json` are generated by the included import tools from a vendored PokeAPI CSV snapshot. The normal application reads those local JSON files and makes no request. See [PokeAPI](https://pokeapi.co/) and its repository for dataset/licensing information. This repository deliberately separates game data, mechanics, and original presentation assets.

## Honest completion checklist

| Area | Current status |
|---|---|
| Runnable GUI and seeded 6v6 battle | **Implemented / tested** |
| 151-species roster, structured move catalog and learnset data | **Implemented / validated** |
| Team builder, import/export, save/load, legality validation | **Implemented (executable move subset only)** |
| Core stats, type chart, damage, status, hazards, screens, weather/terrain subset | **Implemented subset / tested** |
| Moves, abilities and items | **Curated execution subset; catalog data is broader** |
| Mega, Z, Dynamax/Gigantamax, Tera | **Implemented configurable subset; form/move-specific edge cases remain** |
| Fair tactical AI + bounded probabilistic counterplay | **Implemented** |
| Full multi-turn expectiminimax/MCTS, transposition tables, Champion AI | **Not implemented** |
| Every competitive move, ability, item, form and generation interaction | **Not implemented** |
| Full rule editor, replay playback timeline, animation suite, benchmark dashboard | **Partial; planned** |

The project does **not** claim that the remaining broad categories are complete. The next safe extension is expanding the move-effect registry and its interaction tests before exposing those moves in the playable builder.

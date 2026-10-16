"""Typed, UI-independent entities for the authoritative battle engine."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Literal

StatName = Literal["hp", "atk", "def", "spa", "spd", "spe"]
STAT_NAMES: tuple[StatName, ...] = ("hp", "atk", "def", "spa", "spd", "spe")

class Category(str, Enum):
    PHYSICAL = "physical"
    SPECIAL = "special"
    STATUS = "status"

class Status(str, Enum):
    NONE = ""
    BURN = "brn"
    POISON = "psn"
    TOXIC = "tox"
    PARALYSIS = "par"
    SLEEP = "slp"
    FREEZE = "frz"

@dataclass(frozen=True, slots=True)
class Species:
    dex: int
    name: str
    types: tuple[str, ...]
    base_stats: dict[str, int]
    abilities: tuple[str, ...] = ()
    hidden_ability: str | None = None

@dataclass(frozen=True, slots=True)
class Move:
    id: str
    name: str
    type: str
    category: Category
    power: int = 0
    accuracy: int | None = 100
    pp: int = 10
    priority: int = 0
    contact: bool = False
    effect: str = "damage"
    effect_chance: int = 100
    target: str = "foe"
    stat_changes: tuple[tuple[str, int], ...] = ()
    status: Status = Status.NONE
    recoil_fraction: float = 0.0
    drain_fraction: float = 0.0
    flags: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class Nature:
    name: str
    increase: str | None = None
    decrease: str | None = None

@dataclass(frozen=True, slots=True)
class Item:
    id: str
    name: str
    effect: str = ""

@dataclass(slots=True)
class MoveSlot:
    move_id: str
    pp: int
    max_pp: int

@dataclass(slots=True)
class Pokemon:
    species: Species
    nickname: str | None = None
    level: int = 50
    nature: Nature = field(default_factory=lambda: Nature("Hardy"))
    ivs: dict[str, int] = field(default_factory=lambda: {s: 31 for s in STAT_NAMES})
    evs: dict[str, int] = field(default_factory=lambda: {s: 0 for s in STAT_NAMES})
    ability: str | None = None
    item: Item | None = None
    moves: list[MoveSlot] = field(default_factory=list)
    current_hp: int | None = None
    status: Status = Status.NONE
    toxic_counter: int = 0
    stages: dict[str, int] = field(default_factory=lambda: {s: 0 for s in ("atk", "def", "spa", "spd", "spe", "accuracy", "evasion")})
    volatile: dict[str, Any] = field(default_factory=dict)
    revealed_moves: set[str] = field(default_factory=set)
    revealed_item: bool = False
    revealed_ability: bool = False
    fainted: bool = False

    @property
    def label(self) -> str:
        return self.nickname or self.species.name

@dataclass(slots=True)
class Team:
    name: str
    pokemon: list[Pokemon]
    active: int = 0
    hazards: set[str] = field(default_factory=set)
    screens: dict[str, int] = field(default_factory=dict)

    @property
    def active_pokemon(self) -> Pokemon:
        return self.pokemon[self.active]

    def usable_indices(self) -> list[int]:
        return [i for i, mon in enumerate(self.pokemon) if not mon.fainted and (mon.current_hp or 0) > 0]

@dataclass(frozen=True, slots=True)
class MoveAction:
    move_index: int
    phenomenon: str | None = None

@dataclass(frozen=True, slots=True)
class SwitchAction:
    target_index: int

Action = MoveAction | SwitchAction

@dataclass(slots=True)
class BattleRules:
    name: str = "Gen I Roster Tactical Prototype"
    team_size: int = 6
    level_cap: int = 100
    species_clause: bool = False
    ev_cap_per_stat: int = 252
    ev_cap_total: int = 510
    critical_hits: bool = True
    random_damage: bool = True
    allow_mega: bool = False
    allow_z_moves: bool = False
    allow_dynamax: bool = False
    allow_tera: bool = False
    allow_mixed_phenomena: bool = True
    max_mega_per_side: int = 1
    max_z_moves_per_side: int = 1
    dynamax_turns: int = 3
    information_mode: str = "fair"  # fair / omniscient-debug

@dataclass(slots=True)
class BattleEvent:
    turn: int
    text: str
    kind: str = "info"
    data: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class Replay:
    seed: int
    rules: dict[str, Any]
    initial_teams: dict[str, Any]
    actions: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    winner: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

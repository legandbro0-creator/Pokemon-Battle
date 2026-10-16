"""Validated record schemas for JSON imports (plain dataclasses, no third-party dependency).

These replace the former pydantic models so the game runs on platforms where pydantic's
Rust extension is hard to install (e.g. Termux). Validation rules are unchanged.
"""
from __future__ import annotations
from dataclasses import dataclass, field


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass(slots=True)
class SpeciesRecord:
    dex: int
    name: str
    slug: str
    types: list[str]
    base_stats: dict[str, int]
    abilities: list[str] = field(default_factory=list)
    hidden_ability: str | None = None

    def __post_init__(self) -> None:
        _require(isinstance(self.dex, int) and self.dex >= 1, "dex must be an integer >= 1")
        _require(isinstance(self.name, str) and isinstance(self.slug, str), "name and slug must be strings")
        _require(isinstance(self.types, list) and 1 <= len(self.types) <= 2, "types must contain 1-2 entries")
        _require(isinstance(self.base_stats, dict) and all(isinstance(v, int) for v in self.base_stats.values()), "base_stats must map names to integers")
        _require(isinstance(self.abilities, list), "abilities must be a list")

    @classmethod
    def model_validate(cls, data: dict) -> "SpeciesRecord":
        try:
            return cls(**data)
        except TypeError as exc:  # unknown / missing fields
            raise ValueError(f"malformed species record: {exc}") from exc


@dataclass(slots=True)
class MoveRecord:
    id: str
    name: str
    type: str
    category: str
    pp: int
    power: int = 0
    accuracy: int | None = 100

    def __post_init__(self) -> None:
        _require(self.power >= 0, "power must be >= 0")
        _require(self.accuracy is None or 1 <= self.accuracy <= 100, "accuracy must be 1-100 or None")
        _require(1 <= self.pp <= 64, "pp must be 1-64")

    @classmethod
    def model_validate(cls, data: dict) -> "MoveRecord":
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"malformed move record: {exc}") from exc

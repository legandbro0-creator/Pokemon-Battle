"""Probabilistic public-information opponent action model."""
from __future__ import annotations
from dataclasses import dataclass
from engine.content import MOVES
from engine.damage import estimate_damage
from engine.models import Pokemon
from engine.stats import base_stat

@dataclass(frozen=True, slots=True)
class PredictedMove:
    move_id: str
    probability: float
    rationale: str

class OpponentModel:
    def candidate_moves(self, state, actor_side: int, defender: Pokemon, public_actor: Pokemon) -> list[PredictedMove]:
        actual = state.active(actor_side)
        revealed = sorted(actual.revealed_moves)
        # Unknown moves are modeled from publicly plausible supported STAB options, never actual
        # private slots. This is deliberately conservative, rather than omniscient.
        move_ids = revealed or [mid for mid, move in MOVES.items() if move.type in public_actor.species.types and move.category.value != "status"]
        if not move_ids: move_ids = ["tackle"]
        weighted: list[tuple[str, float]] = []
        for move_id in move_ids:
            move = MOVES[move_id]
            damage = estimate_damage(public_actor, defender, move, weather=state.weather, terrain=state.terrain).expected
            weight = max(0.05, damage / max(1, defender.current_hp or base_stat(defender, "hp")))
            if move.priority: weight *= 1.08
            weighted.append((move_id, weight))
        total = sum(weight for _, weight in weighted)
        source = "revealed move" if revealed else "type-based unknown-moveset inference"
        return [PredictedMove(mid, weight / total, source) for mid, weight in weighted]

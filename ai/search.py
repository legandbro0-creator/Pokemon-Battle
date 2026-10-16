"""Bounded public-information predictive evaluator.

This is an anytime one-ply expectation layer used on top of tactical scores. It intentionally
models uncertainty instead of cloning hidden opponent sets. A full multi-turn tree is the next
extension point; `SearchBudget` makes that upgrade API-compatible.
"""
from __future__ import annotations
from dataclasses import dataclass
from engine.content import MOVES
from engine.damage import estimate_damage
from engine.models import MoveAction, SwitchAction
from .opponent_model import OpponentModel

@dataclass(frozen=True, slots=True)
class SearchBudget:
    depth: int = 1
    time_ms: int = 35
    beam_width: int = 6

@dataclass(frozen=True, slots=True)
class PredictionResult:
    expected_return_damage: float
    ko_risk: float
    branches: int

class PredictiveSearch:
    def __init__(self, budget: SearchBudget | None = None, opponent_model: OpponentModel | None = None):
        self.budget = budget or SearchBudget(); self.opponent_model = opponent_model or OpponentModel()

    def evaluate_counterplay(self, state, side: int, action, public_foe) -> PredictionResult:
        defender = state.active(side)
        if isinstance(action, SwitchAction): defender = state.teams[side].pokemon[action.target_index]
        elif isinstance(action, MoveAction):
            own_move = MOVES[defender.moves[action.move_index].move_id]
            hit = estimate_damage(defender, public_foe, own_move, weather=state.weather, terrain=state.terrain)
            # A guaranteed KO eliminates the counterplay branch in this lightweight model.
            if hit.minimum >= (public_foe.current_hp or 0): return PredictionResult(0.0, 0.0, 0)
        predictions = self.opponent_model.candidate_moves(state, 1 - side, defender, public_foe)[:self.budget.beam_width]
        expected, ko_risk = 0.0, 0.0
        for predicted in predictions:
            damage = estimate_damage(public_foe, defender, MOVES[predicted.move_id], weather=state.weather, terrain=state.terrain).expected
            expected += predicted.probability * damage
            if damage >= (defender.current_hp or 0): ko_risk += predicted.probability
        return PredictionResult(expected, ko_risk, len(predictions))

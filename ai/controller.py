"""Heuristic, fair-information battle AI for milestone 1.

It scores legal actions using only its own team plus a public projection of the player's
active Pokémon. Hidden moves/items/abilities/EVs are never read in normal mode.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from engine.battle import BattleState
from engine.content import MOVES, NATURES
from engine.damage import estimate_damage
from engine.models import Action, MoveAction, Pokemon, SwitchAction
from engine.stats import base_stat
from engine import phenomena
from .search import PredictiveSearch, SearchBudget
from engine.type_chart import effectiveness

@dataclass(slots=True)
class AIConfig:
    difficulty: str = "normal"  # easy / normal / hard
    switching_weight: float = 1.0
    risk_tolerance: float = 0.5
    randomness: float = 0.04
    consider_switches: bool = True
    information_mode: str = "fair"
    use_phenomena: bool = True
    lookahead_weight: float = 0.35

@dataclass(slots=True)
class Decision:
    action: Action
    score: float
    explanation: str
    alternatives: list[tuple[Action, float]] = field(default_factory=list)

class TacticalAI:
    def __init__(self, config: AIConfig | None = None):
        self.config = config or AIConfig()
        self.search = PredictiveSearch(SearchBudget(depth=1, time_ms=35 if self.config.difficulty == "hard" else 12))

    def choose_action(self, state: BattleState, side: int = 1) -> Decision:
        legal = state.legal_actions(side)
        if self.config.use_phenomena and self.config.difficulty in {"hard", "expert", "champion"}:
            for action in list(legal):
                if not isinstance(action, MoveAction): continue
                base_move = MOVES[state.active(side).moves[action.move_index].move_id]
                if base_move.category.value == "status": continue
                for phenomenon in state.legal_phenomena(side):
                    candidate = MoveAction(action.move_index, phenomenon)
                    try: state.validate_action(side, candidate)
                    except Exception: continue
                    legal.append(candidate)
        if not legal: raise ValueError("AI was asked to act with no legal actions")
        scored = [(action, self._score(state, side, action)) for action in legal]
        scored.sort(key=lambda entry: entry[1][0], reverse=True)
        if self.config.difficulty == "easy":
            # Easy still legal and matchup-aware, but allows a deliberately bounded suboptimal choice.
            candidates = scored[:min(3, len(scored))]
            choice = candidates[state.rng.randrange(len(candidates))] if state.rng.random() < 0.45 else candidates[0]
        else:
            choice = scored[0]
        action, (score, explanation) = choice
        alternatives = [(a, round(s[0], 1)) for a, s in scored[1:4]]
        return Decision(action, score, explanation, alternatives)

    def choose_replacement(self, state: BattleState, side: int = 1) -> int:
        legal = [a for a in state.legal_actions(side) if isinstance(a, SwitchAction)]
        if not legal: raise ValueError("No legal replacement")
        return max(legal, key=lambda a: self._switch_score(state, side, a.target_index)[0]).target_index

    def _score(self, state: BattleState, side: int, action: Action) -> tuple[float, str]:
        if isinstance(action, SwitchAction): return self._switch_score(state, side, action.target_index)
        user, foe = state.active(side), self._public_projection(state, 1 - side)
        base_move = MOVES[user.moves[action.move_index].move_id]
        if base_move.category.value == "status":
            return self._status_score(state, side, action.move_index)
        move = phenomena.activated_move(base_move, action.phenomenon, user)
        result = estimate_damage(user, foe, move, weather=state.weather, terrain=state.terrain)
        target_hp = max(1, foe.current_hp or 1)
        score = result.expected / target_hp * 100 * (move.accuracy or 100) / 100
        details = [f"expected {result.minimum}-{result.maximum} damage"]
        if result.type_multiplier == 0: return -1000, f"Avoided {move.name}: it cannot affect the target."
        if result.type_multiplier > 1:
            score += 20 * result.type_multiplier; details.append("favorable type matchup")
        if result.minimum >= target_hp:
            score += 180; details.append("guaranteed knockout")
        elif result.maximum >= target_hp:
            score += 65; details.append("possible knockout")
        if move.priority > 0: score += 6
        if move.drain_fraction: score += 8
        if move.effect == "pivot": score += 4
        if action.phenomenon:
            score += {"z": 22, "dynamax": 16, "gigantamax": 17, "mega": 12, "tera": 8}.get(action.phenomenon, 0)
            details.append(f"uses {action.phenomenon} resource")
        incoming = self._expected_incoming(state, side, user)
        if incoming >= (user.current_hp or 1) and result.maximum < target_hp:
            score -= 35 * (1 - self.config.risk_tolerance); details.append("exposed to a likely return knockout")
        if self.config.difficulty in {"hard", "expert", "champion"}:
            prediction = self.search.evaluate_counterplay(state, side, action, foe)
            score -= prediction.expected_return_damage / max(1, user.current_hp or 1) * 18 * self.config.lookahead_weight
            score -= prediction.ko_risk * 20 * (1 - self.config.risk_tolerance)
            if prediction.branches: details.append(f"modeled {prediction.branches} probable replies")
        prefix = f"Activate {action.phenomenon} and use" if action.phenomenon else "Use"
        return score, f"{prefix} {move.name}: " + ", ".join(details) + "."

    def _status_score(self, state: BattleState, side: int, move_index: int) -> tuple[float, str]:
        user, foe_actual = state.active(side), state.active(1 - side)
        move = MOVES[user.moves[move_index].move_id]
        foe = self._public_projection(state, 1 - side)
        hp_ratio = (user.current_hp or 0) / max(1, base_stat(user, "hp"))
        if move.effect in {"heal", "rest"}:
            if hp_ratio < .5: return 52, f"Use {move.name}: recovery materially improves survival."
            return 2, f"Avoid {move.name}: current HP is already healthy."
        if move.effect == "boost":
            # Setup is lower priority while facing immediate public pressure.
            incoming = self._expected_incoming(state, side, user)
            score = 35 - (45 if incoming > (user.current_hp or 1) * .45 else 0)
            return score, f"Use {move.name}: create a stronger future attacking position."
        if move.effect == "protect":
            return (24 if hp_ratio < .45 else 8), f"Use Protect to scout or gain a residual turn."
        if move.effect == "hazard":
            bench = len([m for m in state.teams[1-side].pokemon if not m.fainted]) - 1
            return (30 + bench * 5), "Set Stealth Rock: it pressures the opposing bench on future switches."
        if move.effect in {"status", "sleep"}:
            if foe_actual.status.value: return -4, f"Avoid {move.name}: foe already has a major status."
            score = 33 if move.status.value in {"slp", "par", "brn", "tox"} else 12
            return score, f"Use {move.name}: status reduces the foe's long-term effectiveness."
        return 0, f"Use {move.name}."

    def _switch_score(self, state: BattleState, side: int, index: int) -> tuple[float, str]:
        incoming = state.teams[side].pokemon[index]
        foe = self._public_projection(state, 1 - side)
        max_threat = self._expected_incoming(state, side, incoming)
        hp = max(1, incoming.current_hp or 1)
        score = 30 - max_threat / hp * 70
        # Reward own immediate offensive pressure after switch.
        best = 0.0
        for slot in incoming.moves:
            result = estimate_damage(incoming, foe, MOVES[slot.move_id], weather=state.weather, terrain=state.terrain)
            best = max(best, result.expected / max(1, foe.current_hp or 1) * 30)
        score += best * self.config.switching_weight
        if incoming.item and incoming.item.effect == "boots": score += 3
        return score, f"Switch to {incoming.label}: it is projected to take less damage and retain counterplay."

    def _expected_incoming(self, state: BattleState, side: int, defender: Pokemon) -> float:
        """Use public moves only; if none are revealed, model generic same-type attacks."""
        foe_actual = state.active(1 - side)
        foe = self._public_projection(state, 1 - side)
        move_ids = list(foe_actual.revealed_moves)
        if not move_ids:
            # A type-based archetype is an inference, not access to the foe's private moveset.
            move_ids = [mid for mid, m in MOVES.items() if m.type in foe.species.types and m.category.value != "status"]
        if not move_ids: move_ids = ["tackle"]
        estimates = [estimate_damage(foe, defender, MOVES[mid], weather=state.weather, terrain=state.terrain).expected for mid in move_ids]
        return max(estimates, default=0.0)

    def _public_projection(self, state: BattleState, target_side: int) -> Pokemon:
        actual = state.active(target_side)
        if self.config.information_mode == "omniscient-debug" or state.rules.information_mode == "omniscient-debug":
            return actual
        # Species, level, current HP, type, public statuses and visible stages are public. Hidden
        # IVs/EVs/nature/item/ability/moves remain unavailable and are substituted with a neutral model.
        ability = actual.ability if actual.revealed_ability else None
        projected = Pokemon(species=actual.species, level=actual.level, nature=NATURES["Hardy"], ability=ability)
        projected.current_hp = actual.current_hp
        projected.status = actual.status
        projected.stages = dict(actual.stages)
        return projected

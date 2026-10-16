"""Turn state machine. No pygame/UI imports are permitted in this module."""
from __future__ import annotations
from dataclasses import asdict
import random
from .content import MOVES
from .damage import rolled_damage, type_multiplier
from .models import Action, BattleEvent, BattleRules, Category, MoveAction, Pokemon, Replay, Status, SwitchAction, Team
from .stats import base_stat, effective_stat, max_hp, effective_types
from . import phenomena
from .type_chart import effectiveness
from .serialization import team_summary

class IllegalAction(ValueError):
    pass

class BattleState:
    """Authoritative mutable state for one reproducible singles battle.

    Phase sequence: player/AI legal action selection -> ordering -> execution -> automatic
    opponent replacement -> residual effects -> termination or forced player replacement.
    """
    def __init__(self, player: Team, opponent: Team, rules: BattleRules | None = None, seed: int = 1):
        self.teams = [player, opponent]
        self.rules = rules or BattleRules()
        self.seed = seed
        self.rng = random.Random(seed)
        self.turn = 0
        self.events: list[BattleEvent] = []
        self.winner: int | None = None
        self.weather: str | None = None
        self.weather_turns: int = 0
        self.terrain: str | None = None
        self.terrain_turns: int = 0
        self.awaiting_player_replacement = False
        self.phenomena_used: list[set[str]] = [set(), set()]
        self.replay = Replay(seed=seed, rules=asdict(self.rules), initial_teams={"player": team_summary(player), "opponent": team_summary(opponent)})
        self._log(f"{player.name} challenges {opponent.name}!", "start")
        self._log(f"{player.active_pokemon.label}, go!", "switch")
        self._log(f"{opponent.name} sent out {opponent.active_pokemon.label}!", "switch")
        self._on_enter(0)
        self._on_enter(1)

    def _log(self, text: str, kind: str = "info", **data) -> None:
        event = BattleEvent(self.turn, text, kind, data)
        self.events.append(event)
        self.replay.events.append(asdict(event))

    def active(self, side: int) -> Pokemon:
        return self.teams[side].active_pokemon

    def is_over(self) -> bool:
        return self.winner is not None

    def legal_actions(self, side: int) -> list[Action]:
        if self.is_over(): return []
        team = self.teams[side]
        mon = team.active_pokemon
        switches = [] if mon.volatile.get("dynamax_turns", 0) else [SwitchAction(i) for i in team.usable_indices() if i != team.active]
        if mon.fainted or (mon.current_hp or 0) <= 0:
            return [SwitchAction(i) for i in team.usable_indices() if i != team.active]
        moves = [MoveAction(i) for i, slot in enumerate(mon.moves) if slot.pp > 0]
        return moves + switches

    def legal_phenomena(self, side: int) -> list[str]:
        """Public-to-owner phenomenon options for the currently active Pokémon."""
        if self.is_over() or self.active(side).fainted: return []
        options = []
        for phenomenon in ("mega", "z", "dynamax", "gigantamax", "tera"):
            allowed, _ = phenomena.can_activate(self.active(side), phenomenon, self.rules, self.phenomena_used[side])
            if allowed and (self.rules.allow_mixed_phenomena or not self.phenomena_used[side]): options.append(phenomenon)
        return options

    def validate_action(self, side: int, action: Action) -> None:
        mon = self.active(side)
        legal = self.legal_actions(side)
        if isinstance(action, MoveAction):
            if not any(isinstance(candidate, MoveAction) and candidate.move_index == action.move_index for candidate in legal):
                raise IllegalAction(f"Illegal move action for side {side}: {action}")
            if action.phenomenon:
                base_move = MOVES[mon.moves[action.move_index].move_id]
                if action.phenomenon in {"z", "dynamax", "gigantamax"} and base_move.category == Category.STATUS:
                    raise IllegalAction("Status Z-Moves and Max Guard are not executable in this build.")
                key = "dynamax" if action.phenomenon == "gigantamax" else action.phenomenon
                allowed, reason = phenomena.can_activate(mon, action.phenomenon, self.rules, self.phenomena_used[side])
                if not allowed: raise IllegalAction(reason)
                if not self.rules.allow_mixed_phenomena and self.phenomena_used[side]:
                    raise IllegalAction("This ruleset permits only one battle phenomenon per side.")
        elif action not in legal:
            raise IllegalAction(f"Illegal action for side {side}: {action}")
        if mon.fainted and not isinstance(action, SwitchAction):
            raise IllegalAction("A fainted active Pokémon must be replaced.")

    def run_turn(self, player_action: Action, opponent_action: Action) -> None:
        """Resolve one ordinary turn. Actions must originate from legal_actions."""
        if self.is_over(): raise IllegalAction("The battle is already over.")
        if self.awaiting_player_replacement:
            raise IllegalAction("Choose a replacement before selecting a turn action.")
        self.validate_action(0, player_action)
        self.validate_action(1, opponent_action)
        self.turn += 1
        self._log(f"— Turn {self.turn} —", "turn")
        for side in (0, 1):
            self.active(side).volatile.pop("protect", None)
            self.active(side).volatile.pop("flinch", None)
        ordered = self._order_actions([(0, player_action), (1, opponent_action)])
        self.replay.actions.append({"turn": self.turn, "player": self._action_dict(player_action), "opponent": self._action_dict(opponent_action)})
        for side, action in ordered:
            if self.is_over(): break
            if self.active(side).fainted: continue
            self._execute(side, action)
            self._check_faints()
            if self.is_over(): break
        if not self.is_over():
            self._residual_phase()
            self._check_faints()
        self._finish_phase()

    def choose_player_replacement(self, action: SwitchAction) -> None:
        if not self.awaiting_player_replacement:
            raise IllegalAction("No player replacement is currently required.")
        self.validate_action(0, action)
        self._switch(0, action.target_index, forced=True)
        self.awaiting_player_replacement = False
        self._finish_phase()

    def _action_dict(self, action: Action) -> dict:
        return {"kind": "move", "index": action.move_index, "phenomenon": action.phenomenon} if isinstance(action, MoveAction) else {"kind": "switch", "index": action.target_index}

    def _order_actions(self, entries: list[tuple[int, Action]]) -> list[tuple[int, Action]]:
        def key(entry: tuple[int, Action]) -> tuple[int, int, float]:
            side, action = entry
            if isinstance(action, SwitchAction): return (6, 0, 0)
            move = MOVES[self.active(side).moves[action.move_index].move_id]
            return (move.priority, 0, effective_stat(self.active(side), "spe"))
        # highest priority/speed first; exactly tied actions use seeded RNG.
        a, b = entries
        ka, kb = key(a), key(b)
        if ka == kb and self.rng.randint(0, 1): return [b, a]
        return sorted(entries, key=key, reverse=True)

    def _execute(self, side: int, action: Action) -> None:
        if isinstance(action, SwitchAction):
            self._switch(side, action.target_index)
            return
        self._use_move(side, action.move_index, action.phenomenon)

    def _switch(self, side: int, target: int, *, forced: bool = False) -> None:
        team = self.teams[side]
        outgoing = team.active_pokemon
        if not forced:
            self._log(f"{team.name} withdrew {outgoing.label}!", "switch")
            if outgoing.ability == "regenerator" and not outgoing.fainted:
                healed = max(1, max_hp(outgoing) // 3)
                outgoing.current_hp = min(max_hp(outgoing), (outgoing.current_hp or 0) + healed)
                self._log(f"{outgoing.label} restored health with Regenerator!", "ability")
        # stages/volatile effects are reset on a normal switch; major status stays.
        outgoing.stages = {key: 0 for key in outgoing.stages}
        outgoing.volatile.clear()
        team.active = target
        incoming = team.active_pokemon
        self._log(f"{team.name} sent out {incoming.label}!", "switch")
        self._apply_entry_hazards(side)
        if not incoming.fainted:
            self._on_enter(side)

    def _on_enter(self, side: int) -> None:
        mon, foe = self.active(side), self.active(1 - side)
        if mon.ability == "intimidate" and not foe.fainted:
            mon.revealed_ability = True
            before = foe.stages["atk"]
            foe.stages["atk"] = max(-6, before - 1)
            self._log(f"{mon.label}'s Intimidate lowered {foe.label}'s Attack!", "ability")

    def _apply_entry_hazards(self, side: int) -> None:
        team, mon = self.teams[side], self.active(side)
        if "stealth-rock" not in team.hazards or (mon.item and mon.item.effect == "boots"):
            return
        multiplier = effectiveness("rock", effective_types(mon))
        amount = max(1, int(max_hp(mon) / 8 * multiplier))
        self._damage(mon, amount)
        self._log(f"Pointed stones dug into {mon.label}! (-{amount})", "hazard")

    def _use_move(self, side: int, index: int, phenomenon: str | None = None) -> None:
        user, target = self.active(side), self.active(1 - side)
        slot = user.moves[index]
        base_move = MOVES[slot.move_id]
        if slot.pp <= 0:
            self._log(f"{user.label} has no PP left for {base_move.name}!", "fail"); return
        if phenomenon:
            message = phenomena.activate(user, phenomenon, self.rules)
            self.phenomena_used[side].add("dynamax" if phenomenon == "gigantamax" else phenomenon)
            self._log(message, "phenomenon", side=side, phenomenon=phenomenon)
        move = phenomena.activated_move(base_move, phenomenon, user)
        if not self._can_act(user): return
        slot.pp -= 1
        user.revealed_moves.add(base_move.id)
        self._log(f"{user.label} used {move.name}!", "move", side=side, move=move.id)
        if move.effect == "protect":
            chain = user.volatile.get("protect_chain", 0)
            success = self.rng.random() < (1 / (2 ** chain))
            if success:
                user.volatile["protect"] = True; user.volatile["protect_chain"] = chain + 1
                self._log(f"{user.label} protected itself!", "effect")
            else:
                user.volatile["protect_chain"] = 0; self._log("But it failed!", "fail")
            return
        user.volatile["protect_chain"] = 0
        if move.effect in {"heal", "rest", "boost"}:
            self._self_effect(user, move); return
        if move.effect in {"screen_reflect", "screen_light"}:
            key = "reflect" if move.effect == "screen_reflect" else "light_screen"
            self.teams[side].screens[key] = 5
            self._log(f"{self.teams[side].name}'s team is protected by {move.name}!", "screen"); return
        if move.effect == "defog":
            for team in self.teams: team.hazards.clear(); team.screens.clear()
            self._log("Defog cleared screens and entry hazards!", "field"); return
        if not self._accuracy_hits(user, target, move):
            self._log("The attack missed!", "miss"); return
        if target.volatile.get("protect"):
            self._log(f"{target.label} protected itself!", "protect"); return
        if move.priority > 0 and self.terrain == "psychic" and "flying" not in effective_types(target) and target.ability != "levitate":
            self._log(f"{target.label} is protected from priority moves by Psychic Terrain!", "terrain"); return
        if move.effect == "hazard":
            opposing = self.teams[1 - side]
            if "stealth-rock" in opposing.hazards: self._log("But pointed stones already float around the foe!", "fail")
            else:
                opposing.hazards.add("stealth-rock"); self._log("Pointed stones float in the air around the foe's team!", "hazard")
            return
        if move.category != Category.STATUS:
            critical = self.rules.critical_hits and self.rng.randrange(24) == 0
            screen = self._screen_multiplier(1 - side, move, critical)
            damage, result = rolled_damage(user, target, move, self.rng, critical=critical, random_damage=self.rules.random_damage, weather=self.weather, terrain=self.terrain, screen=screen)
            if damage == 0:
                self._log(f"It doesn't affect {target.label}…", "immune"); return
            dealt = self._damage(target, damage)
            message = f"{target.label} lost {dealt} HP."
            if critical: message = "A critical hit! " + message
            self._log(message, "damage", amount=dealt)
            if result.type_multiplier > 1: self._log("It's super effective!", "effective")
            elif result.type_multiplier < 1: self._log("It's not very effective…", "resist")
            if move.drain_fraction and dealt:
                healed = self._heal(user, max(1, int(dealt * move.drain_fraction)))
                self._log(f"{user.label} drained {healed} HP!", "heal")
            if user.item and user.item.effect == "life_orb" and dealt and not user.fainted:
                recoil = max(1, max_hp(user) // 10); self._damage(user, recoil)
                self._log(f"{user.label} was hurt by its Life Orb! (-{recoil})", "item")
            if move.recoil_fraction and dealt:
                recoil = max(1, int(dealt * move.recoil_fraction)); self._damage(user, recoil); self._log(f"{user.label} was hurt by recoil!", "recoil")
            if move.effect == "max_move": self._max_move_effect(side, user, target, move)
            if target.fainted: return
            if move.effect == "rapid_spin":
                self.teams[side].hazards.clear(); self._log(f"{user.label} blew away entry hazards!", "effect")
            self._secondary(user, target, move)
            if move.effect == "pivot" and not user.fainted and self.teams[side].usable_indices() != [self.teams[side].active]:
                # Deliberately deterministic in milestone 1; full UI pivot selection is a later state-machine extension.
                choices = [i for i in self.teams[side].usable_indices() if i != self.teams[side].active]
                self._log(f"{user.label} pivoted out!", "pivot")
                self._switch(side, choices[0])
        elif move.effect in {"status", "sleep"}:
            self._apply_status(target, move.status)

    def _self_effect(self, user: Pokemon, move) -> None:
        if move.effect == "heal":
            healed = self._heal(user, max_hp(user) // 2)
            self._log(f"{user.label} restored {healed} HP!", "heal")
        elif move.effect == "rest":
            user.current_hp = max_hp(user); user.status = Status.SLEEP; user.volatile["sleep_turns"] = 2
            self._log(f"{user.label} slept and became healthy!", "status")
        elif move.effect == "boost":
            for stat, amount in move.stat_changes: self._change_stage(user, stat, amount)

    def _secondary(self, user: Pokemon, target: Pokemon, move) -> None:
        if move.effect_chance < 100 and self.rng.randrange(100) >= move.effect_chance: return
        if move.effect == "status": self._apply_status(target, move.status)
        elif move.effect == "lower":
            for stat, amount in move.stat_changes: self._change_stage(target, stat, amount)
        elif move.effect == "flinch":
            target.volatile["flinch"] = True; self._log(f"{target.label} flinched!", "effect")
        elif move.effect == "freeze":
            self._apply_status(target, Status.FREEZE)

    def _max_move_effect(self, side: int, user: Pokemon, target: Pokemon, move) -> None:
        """Implemented generic Max Move secondary field/stat effects."""
        weather_by_type = {"fire": "sun", "water": "rain", "rock": "sand", "ice": "hail"}
        terrain_by_type = {"grass": "grassy", "electric": "electric", "psychic": "psychic", "fairy": "misty"}
        self_boost = {"fighting": "atk", "flying": "spe", "ground": "spd", "steel": "def"}
        target_drop = {"poison": "spa", "dragon": "atk", "ghost": "def", "dark": "spd"}
        if move.type in weather_by_type:
            self.weather = weather_by_type[move.type]; self.weather_turns = 5
            self._log(f"{self.weather.title()} began to fall!", "field")
        elif move.type in terrain_by_type:
            self.terrain = terrain_by_type[move.type]; self.terrain_turns = 5
            self._log(f"{self.terrain.title()} Terrain became active!", "field")
        elif move.type in self_boost:
            self._change_stage(user, self_boost[move.type], 1)
        elif move.type in target_drop:
            self._change_stage(target, target_drop[move.type], -1)

    def _apply_status(self, target: Pokemon, status: Status) -> None:
        grounded = "flying" not in effective_types(target) and target.ability != "levitate"
        if self.terrain == "misty" and grounded:
            self._log(f"Misty Terrain protects {target.label} from status!", "terrain"); return
        if self.terrain == "electric" and grounded and status == Status.SLEEP:
            self._log(f"Electric Terrain keeps {target.label} awake!", "terrain"); return
        if target.status != Status.NONE:
            self._log(f"But {target.label} already has a status condition!", "fail"); return
        if status in (Status.POISON, Status.TOXIC) and ("poison" in target.species.types or "steel" in target.species.types):
            self._log(f"It doesn't affect {target.label}…", "immune"); return
        if status == Status.BURN and "fire" in target.species.types:
            self._log(f"It doesn't affect {target.label}…", "immune"); return
        target.status = status
        if status == Status.SLEEP: target.volatile["sleep_turns"] = self.rng.randint(1, 3)
        self._log(f"{target.label} is {self._status_name(status)}!", "status")

    def _status_name(self, status: Status) -> str:
        return {Status.BURN:"burned", Status.POISON:"poisoned", Status.TOXIC:"badly poisoned", Status.PARALYSIS:"paralyzed", Status.SLEEP:"asleep", Status.FREEZE:"frozen"}[status]

    def _change_stage(self, mon: Pokemon, stat: str, amount: int) -> None:
        old = mon.stages[stat]; new = max(-6, min(6, old + amount)); mon.stages[stat] = new
        if new == old: self._log(f"{mon.label}'s {stat.upper()} won't go any further!", "fail"); return
        direction = "rose" if amount > 0 else "fell"
        self._log(f"{mon.label}'s {stat.upper()} {direction}!", "boost")

    def _can_act(self, user: Pokemon) -> bool:
        if user.volatile.pop("flinch", False): self._log(f"{user.label} flinched and couldn't move!", "fail"); return False
        if user.status == Status.SLEEP:
            turns = user.volatile.get("sleep_turns", 0)
            if turns > 0:
                user.volatile["sleep_turns"] = turns - 1; self._log(f"{user.label} is fast asleep.", "fail"); return False
            user.status = Status.NONE; self._log(f"{user.label} woke up!", "status")
        if user.status == Status.FREEZE:
            if self.rng.randrange(100) < 20: user.status = Status.NONE; self._log(f"{user.label} thawed out!", "status")
            else: self._log(f"{user.label} is frozen solid!", "fail"); return False
        if user.status == Status.PARALYSIS and self.rng.randrange(4) == 0:
            self._log(f"{user.label} is fully paralyzed!", "fail"); return False
        return True

    def _accuracy_hits(self, user: Pokemon, target: Pokemon, move) -> bool:
        if move.accuracy is None: return True
        ua, ta = user.stages["accuracy"], target.stages["evasion"]
        stage = max(-6, min(6, ua - ta))
        numerator, denominator = ((3 + stage), 3) if stage >= 0 else (3, 3 - stage)
        chance = min(100, move.accuracy * numerator / denominator)
        return self.rng.random() * 100 < chance

    def _damage(self, target: Pokemon, amount: int) -> int:
        dealt = min(max(0, target.current_hp or 0), max(0, amount))
        target.current_hp = max(0, (target.current_hp or 0) - dealt)
        if target.current_hp <= 0: target.fainted = True
        return dealt

    def _heal(self, mon: Pokemon, amount: int) -> int:
        before = mon.current_hp or 0; maximum = max_hp(mon)
        mon.current_hp = min(maximum, before + max(0, amount)); return (mon.current_hp or 0) - before

    def _screen_multiplier(self, defending_side: int, move, critical: bool) -> float:
        if critical: return 1.0
        screens = self.teams[defending_side].screens
        if move.category == Category.PHYSICAL and screens.get("reflect", 0): return 0.5
        if move.category == Category.SPECIAL and screens.get("light_screen", 0): return 0.5
        return 1.0

    def _residual_phase(self) -> None:
        for side in (0, 1):
            mon = self.active(side)
            if mon.fainted: continue
            if mon.status == Status.BURN:
                damage = max(1, max_hp(mon) // 16); self._damage(mon, damage); self._log(f"{mon.label} is hurt by its burn! (-{damage})", "residual")
            elif mon.status in (Status.POISON, Status.TOXIC):
                if mon.status == Status.TOXIC: mon.toxic_counter += 1; damage = max(1, max_hp(mon) * mon.toxic_counter // 16)
                else: damage = max(1, max_hp(mon) // 8)
                self._damage(mon, damage); self._log(f"{mon.label} is hurt by poison! (-{damage})", "residual")
            if not mon.fainted and mon.item and mon.item.effect == "leftovers":
                healed = self._heal(mon, max(1, max_hp(mon) // 16))
                if healed: self._log(f"{mon.label} restored HP with its Leftovers! (+{healed})", "item")
        self._field_residuals()

    def _field_residuals(self) -> None:
        for team in self.teams:
            for screen in list(team.screens):
                team.screens[screen] -= 1
                if team.screens[screen] <= 0:
                    del team.screens[screen]; self._log(f"{team.name}'s {screen.replace('_', ' ')} wore off!", "screen")
        for side in (0, 1):
            mon = self.active(side)
            if mon.fainted: continue
            if self.weather == "sand" and not any(t in {"rock", "ground", "steel"} for t in effective_types(mon)):
                damage = max(1, max_hp(mon) // 16); self._damage(mon, damage); self._log(f"{mon.label} is buffeted by the sandstorm! (-{damage})", "weather")
            elif self.weather == "hail" and "ice" not in effective_types(mon):
                damage = max(1, max_hp(mon) // 16); self._damage(mon, damage); self._log(f"{mon.label} is pelted by hail! (-{damage})", "weather")
            if not mon.fainted and self.terrain == "grassy" and "flying" not in effective_types(mon) and mon.ability != "levitate":
                healed = self._heal(mon, max(1, max_hp(mon) // 16))
                if healed: self._log(f"{mon.label} restored HP in Grassy Terrain! (+{healed})", "terrain")
            message = phenomena.end_of_turn(mon)
            if message: self._log(message, "phenomenon")
        if self.weather_turns:
            self.weather_turns -= 1
            if self.weather_turns == 0: self._log("The weather returned to normal.", "weather"); self.weather = None
        if self.terrain_turns:
            self.terrain_turns -= 1
            if self.terrain_turns == 0: self._log("The terrain returned to normal.", "terrain"); self.terrain = None

    def _check_faints(self) -> None:
        for side in (0, 1):
            mon = self.active(side)
            if mon.fainted and not mon.volatile.get("faint_announced"):
                mon.volatile["faint_announced"] = True; self._log(f"{mon.label} fainted!", "faint")
        for side in (0, 1):
            if not self.teams[side].usable_indices(): self.winner = 1 - side
        if self.winner is not None:
            self.replay.winner = self.winner; self._log(f"{self.teams[self.winner].name} wins the battle!", "victory")

    def _finish_phase(self) -> None:
        if self.is_over(): return
        # AI replacement is private/automatic; player receives a genuine replacement choice in the GUI.
        if self.active(1).fainted:
            choices = [i for i in self.teams[1].usable_indices() if i != self.teams[1].active]
            if choices: self._switch(1, choices[0], forced=True)
        if self.active(0).fainted:
            self.awaiting_player_replacement = True
            self._log("Choose a replacement Pokémon.", "forced_switch")
        self._check_faints()

    def save_replay(self, path) -> None:
        import json
        from pathlib import Path
        Path(path).write_text(json.dumps(self.replay.to_dict(), indent=2), encoding="utf-8")

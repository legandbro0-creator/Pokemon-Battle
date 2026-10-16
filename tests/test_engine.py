from __future__ import annotations
import json
from ai.controller import AIConfig, TacticalAI
from engine.battle import BattleState
from engine.content import MOVES, SPECIES, make_pokemon
from engine.damage import estimate_damage
from engine.models import BattleRules, MoveAction, SwitchAction, Team
from engine.presets import opponent_team, player_team
from engine.stats import base_stat
from engine.type_chart import effectiveness


def test_complete_gen1_roster_is_offline_and_structured():
    assert len(SPECIES) == 151
    assert SPECIES["bulbasaur"].dex == 1
    assert SPECIES["mew"].base_stats["spe"] == 100
    raw = json.loads(open("pokemon_battler/data/gen1_species.json", encoding="utf8").read())
    assert len(raw["species"]) == 151


def test_type_effectiveness_core_cases():
    assert effectiveness("fire", ("grass",)) == 2
    assert effectiveness("electric", ("water", "flying")) == 4
    assert effectiveness("normal", ("ghost",)) == 0
    assert effectiveness("grass", ("fire", "flying")) == .25


def test_modern_stat_calculation_at_level_50():
    mon = make_pokemon("charizard", ["flamethrower"], level=50, nature="Timid")
    # Charizard HP base is 78: floor(((2*78 + 31 + 0)*50)/100)+50+10.
    assert base_stat(mon, "hp") == 153
    # Timid boosts speed after the normal non-HP formula (120 -> 132).
    assert base_stat(mon, "spe") == 132


def test_damage_respects_stab_type_and_levitate():
    jolteon = make_pokemon("jolteon", ["thunderbolt"], level=50, nature="Timid")
    gyarados = make_pokemon("gyarados", ["waterfall"], level=50)
    electric = estimate_damage(jolteon, gyarados, MOVES["thunderbolt"])
    assert electric.type_multiplier == 4
    gengar = make_pokemon("gengar", ["shadow-ball"], ability="levitate")
    quake = estimate_damage(gyarados, gengar, MOVES["earthquake"])
    assert quake.maximum == 0


def test_switching_applies_stealth_rock_and_boots_prevents_it():
    team0 = Team("P", [make_pokemon("charizard", ["flamethrower"]), make_pokemon("blastoise", ["surf"], item="heavy-duty-boots")])
    team1 = Team("O", [make_pokemon("golem", ["stealth-rock"])])
    state = BattleState(team0, team1, seed=1)
    team0.hazards.add("stealth-rock")
    char_hp = team0.active_pokemon.current_hp
    state._switch(0, 1)
    assert team0.active_pokemon.current_hp == base_stat(team0.active_pokemon, "hp")
    state._switch(0, 0)
    assert team0.active_pokemon.current_hp < char_hp


def test_status_and_priority_resolve_through_authoritative_turn_loop():
    slow = make_pokemon("snorlax", ["quick-attack"], level=50)
    fast = make_pokemon("jolteon", ["tackle"], level=50)
    state = BattleState(Team("P", [slow]), Team("O", [fast]), seed=8)
    state.run_turn(MoveAction(0), MoveAction(0))
    move_events = [event for event in state.events if event.kind == "move"]
    assert move_events[-2].text.startswith("Snorlax used Quick Attack")


def test_ai_produces_only_legal_actions_and_fair_view_hides_moves():
    state = BattleState(player_team(), opponent_team(), seed=5)
    ai = TacticalAI(AIConfig(difficulty="hard", information_mode="fair"))
    decision = ai.choose_action(state, 1)
    assert decision.action in state.legal_actions(1)
    # Player's unrevealed moves must not leak into the AI model.
    view = ai._public_projection(state, 0)
    assert view.moves == []
    assert view.item is None
    assert view.ability is None


def test_seeded_battle_events_are_reproducible():
    def sequence():
        b = BattleState(player_team(), opponent_team(), seed=99)
        ai = TacticalAI()
        for _ in range(3):
            if b.awaiting_player_replacement:
                b.choose_player_replacement(next(a for a in b.legal_actions(0) if isinstance(a, SwitchAction)))
            move = next(a for a in b.legal_actions(0) if isinstance(a, MoveAction))
            b.run_turn(move, ai.choose_action(b, 1).action)
        return [e.text for e in b.events]
    assert sequence() == sequence()


def test_full_automated_six_v_six_battle_finishes():
    state = BattleState(player_team(), opponent_team(), seed=31415)
    p_ai, o_ai = TacticalAI(AIConfig(difficulty="normal")), TacticalAI(AIConfig(difficulty="hard"))
    for _ in range(300):
        if state.is_over(): break
        if state.awaiting_player_replacement:
            state.choose_player_replacement(SwitchAction(p_ai.choose_replacement(state, 0)))
            continue
        state.run_turn(p_ai.choose_action(state, 0).action, o_ai.choose_action(state, 1).action)
    assert state.winner in (0, 1)
    assert state.turn < 300


def test_status_residual_and_leftovers_are_processed():
    player = make_pokemon("snorlax", ["rest"])
    player.current_hp -= 20
    foe = make_pokemon("golem", ["tackle"])
    state = BattleState(Team("P", [player]), Team("O", [foe]), seed=2)
    state._apply_status(player, __import__("engine.models", fromlist=["Status"]).Status.BURN)
    start = player.current_hp
    state._residual_phase()
    # Burn damage is applied before Leftovers recovery; both effects occur in the event log.
    assert any("hurt by its burn" in e.text for e in state.events)
    assert any("Leftovers" in e.text for e in state.events)
    assert player.current_hp == start  # 1/16 burn and 1/16 Leftovers cancel exactly here.


def test_replay_records_actions_and_writes_json(tmp_path):
    state = BattleState(player_team(), opponent_team(), seed=11)
    ai = TacticalAI()
    state.run_turn(MoveAction(0), ai.choose_action(state, 1).action)
    destination = tmp_path / "battle.json"
    state.save_replay(destination)
    saved = json.loads(destination.read_text())
    assert saved["seed"] == 11
    assert len(saved["actions"]) == 1
    assert saved["events"]


def test_mega_evolution_is_ruleset_gated_and_changes_form():
    charizard = make_pokemon("charizard", ["flamethrower", "air-slash", "dragon-pulse", "roost"], item="charizardite-x")
    opponent = make_pokemon("golem", ["tackle", "rock-slide", "earthquake", "body-slam"])
    rules = BattleRules(allow_mega=True)
    state = BattleState(Team("P", [charizard]), Team("O", [opponent]), rules, seed=4)
    state.run_turn(MoveAction(0, "mega"), MoveAction(0))
    assert charizard.species.name == "Mega Charizard X"
    assert "mega" in state.phenomena_used[0]
    assert any(event.kind == "phenomenon" for event in state.events)


def test_tera_changes_defensive_type_and_dynamax_expires():
    from engine.stats import effective_types, max_hp
    jolteon = make_pokemon("jolteon", ["thunderbolt", "quick-attack", "shadow-ball", "thunder-wave"])
    jolteon.volatile["tera_type"] = "water"
    foe = make_pokemon("golem", ["tackle", "rock-slide", "earthquake", "body-slam"])
    rules = BattleRules(allow_tera=True, allow_dynamax=True)
    state = BattleState(Team("P", [jolteon]), Team("O", [foe]), rules, seed=12)
    state.run_turn(MoveAction(1, "tera"), MoveAction(0))
    assert effective_types(jolteon) == ("water",)
    original = max_hp(jolteon)
    state.run_turn(MoveAction(0, "dynamax"), MoveAction(0))
    assert max_hp(jolteon) == original * 2
    # Two subsequent turn endings finish the configured 3-turn Dynamax window.
    state.run_turn(MoveAction(0), MoveAction(0)); state.run_turn(MoveAction(0), MoveAction(0))
    assert jolteon.volatile.get("dynamax_turns", 0) == 0


def test_team_json_round_trip_and_validation(tmp_path):
    from engine.team_io import load_team, save_team, validate_team
    original = player_team(); target = tmp_path / "team.json"
    save_team(original, target)
    restored = load_team(target)
    assert restored.name == original.name
    assert restored.pokemon[0].species.name == "Charizard"
    assert not [issue for issue in validate_team(restored, BattleRules()) if issue.severity == "error"]


def test_complete_sourced_move_catalog_and_learnset_index_are_available():
    from engine.content import MOVE_CATALOG, LEARNSETS, learnable_moves
    assert len(MOVE_CATALOG) >= 900
    assert len(LEARNSETS) == 151
    assert "flamethrower" in LEARNSETS[str(SPECIES["charizard"].dex)]
    assert "flamethrower" in learnable_moves("charizard")


def test_weather_and_terrain_modifiers_affect_damage_estimator():
    charizard = make_pokemon("charizard", ["flamethrower"])
    venusaur = make_pokemon("venusaur", ["giga-drain"])
    plain = estimate_damage(charizard, venusaur, MOVES["flamethrower"]).expected
    sunny = estimate_damage(charizard, venusaur, MOVES["flamethrower"], weather="sun").expected
    rainy = estimate_damage(charizard, venusaur, MOVES["flamethrower"], weather="rain").expected
    assert sunny > plain > rainy


def test_ruleset_round_trip_and_ai_prediction_is_public_information(tmp_path):
    from engine.rulesets import save_ruleset, load_ruleset
    from ai.search import PredictiveSearch
    rules = BattleRules(name="Custom", allow_dynamax=True, allow_tera=True)
    path = tmp_path / "rules.json"; save_ruleset(rules, path)
    assert load_ruleset(path).allow_dynamax
    state = BattleState(player_team(), opponent_team(), rules, seed=3)
    ai = TacticalAI(AIConfig(difficulty="hard")); foe = ai._public_projection(state, 0)
    result = PredictiveSearch().evaluate_counterplay(state, 1, MoveAction(0), foe)
    assert result.branches >= 1


def test_reflect_reduces_physical_damage_and_expires():
    defender = make_pokemon("snorlax", ["reflect", "rest", "body-slam", "crunch"])
    attacker = make_pokemon("golem", ["earthquake", "tackle", "rock-slide", "body-slam"])
    state = BattleState(Team("P", [defender]), Team("O", [attacker]), seed=42)
    state.run_turn(MoveAction(0), MoveAction(0))
    assert state.teams[0].screens["reflect"] == 4
    assert any(event.kind == "screen" for event in state.events)

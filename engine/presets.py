"""Playable, legal-looking Gen I roster demonstration teams for the prototype."""
from __future__ import annotations
from .content import make_pokemon
from .models import Team

def player_team() -> Team:
    return Team("Player", [
        make_pokemon("charizard", ["flamethrower", "air-slash", "dragon-pulse", "roost"], nature="Timid", item="life-orb"),
        make_pokemon("venusaur", ["giga-drain", "sludge-bomb", "sleep-powder", "synthesis"], nature="Modest"),
        make_pokemon("blastoise", ["surf", "ice-beam", "rapid-spin", "protect"], nature="Modest"),
        make_pokemon("jolteon", ["thunderbolt", "volt-switch", "shadow-ball", "thunder-wave"], nature="Timid"),
        make_pokemon("snorlax", ["body-slam", "earthquake", "crunch", "rest"], nature="Adamant"),
        make_pokemon("gengar", ["shadow-ball", "sludge-bomb", "thunderbolt", "will-o-wisp"], nature="Timid", ability="levitate"),
    ])

def opponent_team() -> Team:
    return Team("Tactical AI", [
        make_pokemon("gyarados", ["waterfall", "ice-fang", "dragon-dance", "earthquake"], nature="Jolly", ability="intimidate"),
        make_pokemon("golem", ["earthquake", "rock-slide", "stealth-rock", "body-slam"], nature="Adamant"),
        make_pokemon("exeggutor", ["psychic", "giga-drain", "sleep-powder", "synthesis"], nature="Modest"),
        make_pokemon("dragonite", ["dragon-claw", "earthquake", "fire-punch", "roost"], nature="Adamant"),
        make_pokemon("alakazam", ["psychic", "shadow-ball", "focus-blast", "recover"], nature="Timid"),
        make_pokemon("mewtwo", ["psychic", "ice-beam", "aura-sphere", "recover"], nature="Timid", item="life-orb"),
    ])

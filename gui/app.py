from __future__ import annotations
import math
from pathlib import Path
import pygame
from ai.controller import AIConfig, TacticalAI
from engine.battle import BattleState, IllegalAction
from engine.content import MOVES, SPECIES, learnable_moves, make_pokemon
from engine.models import MoveAction, SwitchAction, MoveSlot, STAT_NAMES
from engine.presets import opponent_team, player_team
from engine.rulesets import PRESETS
from engine.team_io import load_team, save_team, team_from_dict, team_to_dict, validate_team
from engine.stats import all_stats, base_stat, max_hp, effective_types
from .sprites import SpriteBook

WIDTH, HEIGHT = 1280, 760
BG = (13, 19, 31); PANEL = (25, 35, 54); PANEL2 = (34, 48, 72)
TEXT = (232, 239, 248); MUTED = (154, 172, 195); ACCENT = (77, 190, 199)
DANGER = (234, 93, 101); HP = (84, 203, 130); TYPE_COLORS = {
    'fire': (233, 112, 68), 'water': (74, 143, 222), 'grass': (93, 178, 95), 'electric': (233, 195, 66),
    'normal': (171, 166, 143), 'flying': (128, 153, 224), 'poison': (165, 91, 180), 'ground': (200, 163, 87),
    'rock': (177, 152, 86), 'psychic': (223, 95, 143), 'ghost': (107, 91, 158), 'ice': (102, 198, 202),
    'dragon': (103, 83, 209), 'dark': (104, 85, 74), 'steel': (150, 165, 177), 'bug': (156, 178, 54),
    'fighting': (190, 67, 59), 'fairy': (225, 147, 205),
}

class App:
    def __init__(self):
        pygame.init(); pygame.display.set_caption("Pokémon — Tactical Battle Prototype")
        window_icon = SpriteBook.window_icon()
        if window_icon is not None: pygame.display.set_icon(window_icon)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        self.sprites = SpriteBook()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("dejavusans", 16)
        self.small = pygame.font.SysFont("dejavusans", 13)
        self.title = pygame.font.SysFont("dejavusans", 28, bold=True)
        self.big = pygame.font.SysFont("dejavusans", 38, bold=True)
        self.scene = "menu"; self.running = True; self.buttons: list[tuple[pygame.Rect, object]] = []
        self.battle: BattleState | None = None; self.ai: TacticalAI | None = None
        self.last_ai_explanation = ""; self.show_analysis = False; self.roster_page = 0
        self.builder_team = player_team(); self.builder_slot = 0; self.builder_page = 0; self.builder_move_slot = 0
        self.rules = PRESETS["competitive"]; self.ai_difficulty = "hard"; self.builder_message = ""
        self.selected_phenomenon: str | None = None; self.history: list[dict] = []; self.history_recorded = False

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False
                elif event.type == pygame.KEYDOWN: self._key(event)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: self._click(event.pos)
            self._draw()
            pygame.display.flip(); self.clock.tick(60)
        pygame.quit()

    def _key(self, event):
        if event.key == pygame.K_ESCAPE:
            if self.scene == "menu": self.running = False
            else: self.scene = "menu"
        if self.scene == "battle" and event.key == pygame.K_a: self.show_analysis = not self.show_analysis
        if self.scene == "roster":
            if event.key == pygame.K_RIGHT: self.roster_page = min(5, self.roster_page + 1)
            if event.key == pygame.K_LEFT: self.roster_page = max(0, self.roster_page - 1)
        if self.scene == "builder":
            if event.key == pygame.K_RIGHT: self.builder_page = min(5, self.builder_page + 1)
            if event.key == pygame.K_LEFT: self.builder_page = max(0, self.builder_page - 1)

    def _click(self, pos):
        for rect, payload in reversed(self.buttons):
            if rect.collidepoint(pos):
                if callable(payload): payload()
                else: self._battle_action(payload)
                return

    def _start_battle(self):
        issues = [issue for issue in validate_team(self.builder_team, self.rules) if issue.severity == "error"]
        if issues:
            self.builder_message = "Cannot start: " + issues[0].message
            self.scene = "builder"; return
        # A serialise/deserialise round-trip gives the battle an isolated mutable team state.
        battle_team = team_from_dict(team_to_dict(self.builder_team))
        self.battle = BattleState(battle_team, opponent_team(), self.rules, seed=20261016)
        self.ai = TacticalAI(AIConfig(difficulty=self.ai_difficulty, switching_weight=1.15, risk_tolerance=.42))
        self.last_ai_explanation = "AI uses a fair-information tactical heuristic. Press A for the live analysis panel."
        self.selected_phenomenon = None; self.history_recorded = False; self.scene = "battle"

    def _battle_action(self, action):
        if not self.battle or self.battle.is_over(): return
        try:
            if self.battle.awaiting_player_replacement:
                if isinstance(action, SwitchAction): self.battle.choose_player_replacement(action)
                return
            if not isinstance(action, (MoveAction, SwitchAction)): return
            decision = self.ai.choose_action(self.battle, 1)
            self.last_ai_explanation = decision.explanation
            self.battle.run_turn(action, decision.action)
            self.selected_phenomenon = None
            if self.battle.is_over(): self._record_history()
        except IllegalAction as exc:
            self.last_ai_explanation = f"Action rejected: {exc}"

    def _record_history(self):
        if not self.battle or self.history_recorded: return
        self.history_recorded = True
        self.history.append({"turns": self.battle.turn, "winner": self.battle.winner, "rules": self.rules.name, "events": [event.text for event in self.battle.events], "seed": self.battle.seed})
        Path("replays").mkdir(exist_ok=True)
        self.battle.save_replay(Path("replays") / f"battle_{self.battle.seed}_{len(self.history)}.json")

    def _draw(self):
        self.screen.fill(BG); self.buttons = []
        if self.scene == "menu": self._menu()
        elif self.scene == "battle": self._battle_scene()
        elif self.scene == "roster": self._roster()
        elif self.scene == "builder": self._builder()
        elif self.scene == "rules": self._rules_screen()
        elif self.scene == "history": self._history_screen()

    def _menu(self):
        self._starfield()
        self._text("POKÉMON", (70, 72), self.big, (245, 207, 75))
        self._text("TACTICAL BATTLE SIMULATOR", (72, 118), self.title, ACCENT)
        self._text("Phase 1 • offline 6v6 tactical prototype • Gen III sprites", (73, 152), self.font, MUTED)
        descriptions = [
            ("PLAY TACTICAL BATTLE", "Battle with the team currently configured in Team Builder", self._start_battle),
            ("TEAM BUILDER", "Choose from all 151 species, executable sourced moves, and save/load JSON", lambda: setattr(self, "scene", "builder")),
            ("BATTLE RULES & AI", "Configure phenomena, clauses, and AI difficulty", lambda: setattr(self, "scene", "rules")),
            ("GEN I ROSTER", "Browse the complete offline 151-species structured database", lambda: setattr(self, "scene", "roster")),
            ("BATTLE HISTORY", "Inspect recorded local battle summaries and logs", lambda: setattr(self, "scene", "history")),
            ("EXIT", "Close the application", lambda: setattr(self, "running", False)),
        ]
        y = 200
        for label, desc, handler in descriptions:
            r = pygame.Rect(72, y, 520, 60); self._button(r, label, desc, handler); y += 67
        self._panel(pygame.Rect(680, 95, 510, 470))
        self._text("CURRENT BUILD", (715, 130), self.title)
        lines = ["✓ Complete Gen I roster data (151 species)", "✓ Seeded turn engine, stats, type and damage", "✓ Move choice, switching, fainting and replacement", "✓ Status, boosts, Protect, hazards and residuals", "✓ Strategy-aware legal-action AI", "✓ Replay events saved by the engine", "", "Advanced mechanics, complete learnsets, editor and", "phenomena are roadmap items—not claimed complete."]
        for i, line in enumerate(lines): self._text(line, (715, 184+i*34), self.font, HP if line.startswith("✓") else MUTED)
        self._text("Esc quits", (73, 687), self.small, MUTED)
        self._panel(pygame.Rect(680, 585, 510, 118))
        self._text("YOUR TEAM", (700, 594), self.small, MUTED)
        for i, mon in enumerate(self.builder_team.pokemon):
            icon = self.sprites.pokemon_icon(mon.species.dex, 64)
            if icon: self.screen.blit(icon, (700 + i * 80, 622))

    def _roster(self):
        self._text("GENERATION I ROSTER", (55, 42), self.big)
        self._text("Complete structured species dataset • page %d/6 • ←/→ to navigate • Esc to menu" % (self.roster_page+1), (58, 93), self.font, MUTED)
        entries = sorted(SPECIES.values(), key=lambda s: s.dex)[self.roster_page*30:(self.roster_page+1)*30]
        for n, species in enumerate(entries):
            col, row = n % 3, n // 3
            r = pygame.Rect(55 + col*400, 132 + row*54, 365, 43); self._panel(r, PANEL)
            icon = self.sprites.pokemon_icon(species.dex, 38)
            if icon: self.screen.blit(icon, (r.x+5, r.y+2))
            self._text(f"#{species.dex:03d}  {species.name}", (r.x+48, r.y+8), self.font)
            x = r.x+218
            for type_name in species.types:
                self._chip(type_name.upper(), pygame.Rect(x, r.y+9, 70, 22), type_name); x += 73
        self._text("Source snapshot: PokeAPI CSV. No external connection is used at play time.", (55, 700), self.small, MUTED)

    def _builder(self):
        self._text("TEAM BUILDER", (38, 25), self.big)
        self._text("All species and full sourced learnsets are browsable; only the curated executable move set can enter a playable battle.", (40, 75), self.small, MUTED)
        self._panel(pygame.Rect(28, 108, 385, 610))
        self._text("TEAM SLOTS", (48, 127), self.title)
        for index, mon in enumerate(self.builder_team.pokemon):
            r = pygame.Rect(47, 169 + index * 61, 347, 52)
            detail = f"{' / '.join(mon.species.types).upper()}  •  {len(mon.moves)}/4 moves  •  Lv {mon.level}"
            self._button(r, f"{index+1}. {mon.label}", detail, lambda index=index: setattr(self, "builder_slot", index), accent=ACCENT if index == self.builder_slot else TYPE_COLORS.get(mon.species.types[0], ACCENT), icon=self.sprites.pokemon_icon(mon.species.dex, 42))
        self._button(pygame.Rect(47, 551, 164, 46), "SAVE TEAM", "teams/user_team.json", self._save_builder_team)
        self._button(pygame.Rect(230, 551, 164, 46), "LOAD TEAM", "local JSON", self._load_builder_team)
        self._button(pygame.Rect(47, 611, 347, 46), "VALIDATE & PLAY", "checks rules then opens battle", self._start_battle, accent=HP)
        if self.builder_message: self._text(self.builder_message[:47], (49, 677), self.small, DANGER if "Cannot" in self.builder_message else HP)

        mon = self.builder_team.pokemon[self.builder_slot]
        self._text(f"EDITING SLOT {self.builder_slot+1}: {mon.label.upper()}", (445, 113), self.title)
        self._text(f"Types: {' / '.join(mon.species.types).upper()}   Ability: {mon.ability or '—'}   Item: {mon.item.name if mon.item else 'None'}", (447, 149), self.font, MUTED)
        for i, stat in enumerate(("hp", "atk", "def", "spa", "spd", "spe")):
            self._text(f"{stat.upper()} {base_stat(mon, stat)}", (448 + (i % 3) * 136, 180 + (i // 3) * 27), self.small)
        self._button(pygame.Rect(447, 236, 160, 45), "ABILITY", mon.ability or "none", self._cycle_ability)
        self._button(pygame.Rect(617, 236, 160, 45), "HELD ITEM", mon.item.name if mon.item else "None", self._cycle_item, icon=self.sprites.item(mon.item.id, 28) if mon.item else None)
        if not self.sprites.draw_pokemon(self.screen, mon.species.dex, "front", (1085, 226), 2.0):
            self._draw_mon_marker(mon, (1085, 160))
        self._button(pygame.Rect(787, 236, 160, 45), "OFFENSE EVS", "252 Atk / 252 Spe", self._offensive_evs)
        self._button(pygame.Rect(957, 236, 260, 45), "TERA TYPE", mon.volatile.get("tera_type", mon.species.types[0]).upper(), self._cycle_tera_type)
        self._text("MOVE SLOTS — click a slot, then choose an executable learned move", (447, 304), self.font, ACCENT)
        for index in range(4):
            label = MOVES[mon.moves[index].move_id].name if index < len(mon.moves) else "[empty]"
            r = pygame.Rect(447 + (index % 2) * 240, 333 + (index // 2) * 47, 228, 38)
            self._button(r, label, "", lambda index=index: setattr(self, "builder_move_slot", index), accent=ACCENT if index == self.builder_move_slot else PANEL2)
        executable = learnable_moves(next(slug for slug, species in SPECIES.items() if species.dex == mon.species.dex), executable_only=True)
        self._text(f"EXECUTABLE LEARNED MOVES ({len(executable)})", (447, 422), self.font, ACCENT)
        for index, move_id in enumerate(executable[:10]):
            move = MOVES[move_id]; col, row = index % 5, index // 5
            self._button(pygame.Rect(447 + col * 154, 447 + row * 41, 144, 35), move.name, "", lambda move_id=move_id: self._set_builder_move(move_id), accent=TYPE_COLORS.get(move.type, ACCENT))
        self._text(f"SPECIES BROWSER  •  page {self.builder_page+1}/6  •  ←/→ keys", (447, 536), self.font, ACCENT)
        species_entries = sorted(SPECIES.items(), key=lambda pair: pair[1].dex)[self.builder_page*30:(self.builder_page+1)*30]
        for index, (slug, species) in enumerate(species_entries):
            col, row = index % 6, index // 6
            self._button(pygame.Rect(447 + col * 128, 568 + row * 34, 123, 32), species.name, "", lambda slug=slug: self._select_species(slug), accent=TYPE_COLORS.get(species.types[0], ACCENT), icon=self.sprites.pokemon_icon(species.dex, 24), font=self.small)

    def _select_species(self, slug: str):
        legal = learnable_moves(slug, executable_only=True)
        # Preserve only actual sourced executable moves. Species with too few currently executable
        # moves remain editable but are blocked by validation rather than receiving invented moves.
        self.builder_team.pokemon[self.builder_slot] = make_pokemon(slug, legal[:4])
        self.builder_move_slot = 0
        self.builder_message = f"Selected {SPECIES[slug].name}. {len(legal)} executable learned move(s) available."

    def _set_builder_move(self, move_id: str):
        mon = self.builder_team.pokemon[self.builder_slot]
        if self.builder_move_slot < len(mon.moves):
            mon.moves[self.builder_move_slot] = MoveSlot(move_id, MOVES[move_id].pp, MOVES[move_id].pp)
        else:
            mon.moves.append(MoveSlot(move_id, MOVES[move_id].pp, MOVES[move_id].pp))
        self.builder_message = f"Set move slot {self.builder_move_slot+1} to {MOVES[move_id].name}."

    def _cycle_ability(self):
        mon = self.builder_team.pokemon[self.builder_slot]; choices = list(mon.species.abilities) + ([mon.species.hidden_ability] if mon.species.hidden_ability else [])
        if not choices: return
        mon.ability = choices[(choices.index(mon.ability) + 1) % len(choices)] if mon.ability in choices else choices[0]

    def _cycle_item(self):
        from engine.content import ITEMS
        mon = self.builder_team.pokemon[self.builder_slot]; options = [None, *ITEMS.values()]
        current = next((i for i, item in enumerate(options) if (item.id if item else None) == (mon.item.id if mon.item else None)), 0)
        mon.item = options[(current + 1) % len(options)]

    def _offensive_evs(self):
        mon = self.builder_team.pokemon[self.builder_slot]; mon.evs = {stat: 0 for stat in STAT_NAMES}; mon.evs["atk"] = 252; mon.evs["spe"] = 252; mon.evs["hp"] = 4

    def _cycle_tera_type(self):
        types = list(TYPE_COLORS); mon = self.builder_team.pokemon[self.builder_slot]; current = mon.volatile.get("tera_type", mon.species.types[0]); mon.volatile["tera_type"] = types[(types.index(current) + 1) % len(types)]

    def _save_builder_team(self):
        save_team(self.builder_team, Path("teams") / "user_team.json"); self.builder_message = "Saved teams/user_team.json"

    def _load_builder_team(self):
        path = Path("teams") / "user_team.json"
        try: self.builder_team = load_team(path); self.builder_slot = 0; self.builder_message = "Loaded teams/user_team.json"
        except Exception as exc: self.builder_message = f"Load failed: {exc}"

    def _rules_screen(self):
        self._text("BATTLE RULES & AI SETTINGS", (45, 35), self.big)
        self._text("These settings are passed into the same authoritative engine and AI—no UI-only rules.", (47, 85), self.font, MUTED)
        self._panel(pygame.Rect(44, 123, 530, 470))
        self._text(self.rules.name, (67, 151), self.title, ACCENT)
        fields = [("allow_mega", "MEGA EVOLUTION"), ("allow_z_moves", "Z-MOVES"), ("allow_dynamax", "DYNAMAX / GMAX"), ("allow_tera", "TERASTALLIZATION"), ("species_clause", "SPECIES CLAUSE"), ("allow_mixed_phenomena", "ALLOW MIXED PHENOMENA")]
        for index, (field, label) in enumerate(fields):
            value = getattr(self.rules, field)
            self._button(pygame.Rect(68, 200 + index * 55, 475, 43), label, "ON" if value else "OFF", lambda field=field: self._toggle_rule(field), accent=HP if value else DANGER)
        self._panel(pygame.Rect(612, 123, 600, 470))
        self._text("AI CONFIGURATION", (638, 151), self.title, ACCENT)
        self._button(pygame.Rect(638, 204, 540, 55), "DIFFICULTY", self.ai_difficulty.upper(), self._cycle_difficulty)
        self._text("Easy: legal, basic type play. Normal: damage and switches.", (640, 297), self.font, MUTED)
        self._text("Hard: hazards/status/switch safety and available battle resources.", (640, 328), self.font, MUTED)
        self._text("Expert/Champion labels reserve future multi-turn search budgets; they are not exposed as completed modes yet.", (640, 359), self.small, DANGER)
        self._button(pygame.Rect(638, 430, 250, 54), "USE COMPETITIVE", "reset rules preset", lambda: self._set_rules("competitive"), accent=ACCENT)
        self._button(pygame.Rect(915, 430, 263, 54), "USE SANDBOX", "all four phenomena", lambda: self._set_rules("national-dex-sandbox"), accent=(218, 148, 226))
        self._text("Esc returns to menu", (48, 676), self.small, MUTED)

    def _toggle_rule(self, field): setattr(self.rules, field, not getattr(self.rules, field))
    def _cycle_difficulty(self): self.ai_difficulty = {"easy":"normal", "normal":"hard", "hard":"easy"}[self.ai_difficulty]
    def _set_rules(self, key):
        from dataclasses import replace
        self.rules = replace(PRESETS[key])

    def _history_screen(self):
        self._text("BATTLE HISTORY", (45, 35), self.big)
        self._text("Completed battles save a deterministic replay JSON under replays/.", (47, 84), self.font, MUTED)
        if not self.history: self._text("No battles recorded in this session yet.", (55, 146), self.title, MUTED)
        for index, record in enumerate(reversed(self.history[-8:])):
            y = 132 + index * 67; self._panel(pygame.Rect(46, y, 1120, 54), PANEL)
            result = "PLAYER VICTORY" if record["winner"] == 0 else "AI VICTORY"
            self._text(f"{result}  •  {record['turns']} turns  •  {record['rules']}  •  seed {record['seed']}", (65, y+10), self.font, HP if record["winner"] == 0 else DANGER)
            self._text(record["events"][-1] if record["events"] else "", (65, y+30), self.small, MUTED)
        self._text("Esc returns to menu", (48, 676), self.small, MUTED)

    def _battle_scene(self):
        b = self.battle
        if not b: return
        self._text("TACTICAL BATTLE", (30, 18), self.title)
        screen_text = " / ".join(f"P:{name.replace('_', ' ')} {turns}" for name, turns in b.teams[0].screens.items())
        field = "  •  ".join(part for part in [f"Weather: {b.weather.title()} ({b.weather_turns})" if b.weather else "", f"Terrain: {b.terrain.title()} ({b.terrain_turns})" if b.terrain else "", screen_text] if part) or "No active field effect"
        self._text(f"TURN {b.turn + (0 if b.awaiting_player_replacement else 1)}  •  {field}  •  A: analysis  •  Esc: menu", (31, 53), self.small, MUTED)
        # Field strip
        self._panel(pygame.Rect(24, 76, 805, 354), PANEL)
        pygame.draw.ellipse(self.screen, (52, 45, 68), pygame.Rect(470, 192, 290, 70))   # foe platform
        pygame.draw.ellipse(self.screen, (30, 54, 62), pygame.Rect(70, 318, 330, 84))    # player platform
        self._mon_card(1, pygame.Rect(48, 100, 300, 98), flip=False)
        self._mon_card(0, pygame.Rect(505, 318, 300, 98), flip=True)
        self._draw_mon_sprite(self.active_safe(1), (615, 234), back=False)
        self._draw_mon_sprite(self.active_safe(0), (235, 364), back=True)
        self._team_strip(1, 52, 208); self._team_strip(0, 509, 284)
        self._controls()
        self._log_panel()
        if self.show_analysis: self._analysis_panel()
        if b.is_over():
            color = HP if b.winner == 0 else DANGER
            self._overlay(f"{'VICTORY' if b.winner == 0 else 'DEFEAT'}", "Click here or Esc to return to menu", color)
            self.buttons.append((pygame.Rect(0, 0, WIDTH, HEIGHT), lambda: setattr(self, "scene", "menu")))

    def active_safe(self, side): return self.battle.active(side)

    def _mon_card(self, side, rect, flip):
        mon = self.battle.active(side); self._panel(rect, PANEL2)
        self._text(mon.label.upper(), (rect.x+12, rect.y+10), self.title)
        self._text(f"Lv. {mon.level}" + (f"  •  {mon.status.value.upper()}" if mon.status.value else ""), (rect.x+14, rect.y+44), self.small, DANGER if mon.status.value else MUTED)
        if mon.item and (side == 0 or mon.revealed_item):
            item_icon = self.sprites.item(mon.item.id, 24)
            if item_icon: self.screen.blit(item_icon, (rect.x + 170, rect.y + 41))
        types = effective_types(mon)
        x = rect.right - 8 - 66 * len(types)
        for typ in types: self._chip(typ.upper(), pygame.Rect(x, rect.y+12, 62, 21), typ); x += 66
        maximum = max_hp(mon); current = max(0, mon.current_hp or 0)
        self._hp_bar(pygame.Rect(rect.x+13, rect.y+70, rect.w-26, 15), current, maximum)
        self._text(f"{current}/{maximum}", (rect.right-80, rect.y+47), self.small, TEXT)

    def _draw_mon_sprite(self, mon, feet, back):
        """Gen III front (foe) / back (player) sprite standing on its platform, with a gentle idle bob."""
        bob = 0 if mon.fainted else round(math.sin(pygame.time.get_ticks() / 380 + (1.7 if back else 0)) * 3)
        if self.sprites.draw_pokemon(self.screen, mon.species.dex, "back" if back else "front", (feet[0], feet[1] + bob), 3 if back else 2.5, faded=mon.fainted):
            return
        self._draw_mon_marker(mon, (feet[0], feet[1] - 70))

    def _draw_mon_marker(self, mon, center):
        # Fallback when a sprite file is missing: the original abstract marker.
        x,y=center; color=TYPE_COLORS.get(mon.species.types[0], ACCENT)
        pygame.draw.circle(self.screen, color, (x,y), 42)
        pygame.draw.circle(self.screen, (10,15,25), (x,y), 28)
        pygame.draw.line(self.screen, color, (x-48,y), (x+48,y), 6)
        self._text(mon.species.name[0], (x-7,y-13), self.title, color)

    def _team_strip(self, side, x, y):
        team=self.battle.teams[side]
        for idx, mon in enumerate(team.pokemon):
            r=pygame.Rect(x+idx*31, y, 24, 24); color=HP if not mon.fainted else (70,76,88)
            ball=self.sprites.item("poke-ball", 24, dim=mon.fainted)
            if ball: self.screen.blit(ball, r)
            else: pygame.draw.circle(self.screen,color,r.center,10)
            if idx==team.active: pygame.draw.circle(self.screen,TEXT,r.center,15,1)

    def _controls(self):
        b=self.battle; area=pygame.Rect(24, 448, 805, 286); self._panel(area)
        if b.awaiting_player_replacement:
            self._text("CHOOSE A REPLACEMENT", (46, 468), self.title, DANGER)
            self._switch_buttons(46, 514, forced=True); return
        self._text("YOUR ACTION", (46, 466), self.title)
        mon=b.active(0)
        actions=b.legal_actions(0)
        for i, action in enumerate(a for a in actions if isinstance(a, MoveAction)):
            move=MOVES[mon.moves[action.move_index].move_id]
            col,row=i%2,i//2; r=pygame.Rect(46+col*365, 508+row*66, 345, 55)
            detail=f"{move.type.upper()}  {move.category.value.upper()}  PP {mon.moves[action.move_index].pp}/{mon.moves[action.move_index].max_pp}"
            payload = MoveAction(action.move_index, self.selected_phenomenon)
            label = (f"[{self.selected_phenomenon.upper()}] " if self.selected_phenomenon else "") + move.name
            self._button(r, label, detail, payload, accent=TYPE_COLORS.get(move.type, ACCENT))
        self._text("SWITCH", (48, 651), self.small, MUTED)
        self._switch_buttons(120, 636, forced=False, compact=True)
        options = b.legal_phenomena(0)
        if options:
            self._text("PHENOMENON", (47, 699), self.small, MUTED)
            for i, name in enumerate(options):
                r = pygame.Rect(145 + i * 126, 688, 117, 35)
                self._button(r, name.upper(), "selected" if self.selected_phenomenon == name else "", lambda name=name: self._toggle_phenomenon(name), accent=(218, 148, 226) if self.selected_phenomenon == name else ACCENT, icon=self.sprites.item({"mega": "mega-ring", "z": "z-crystal"}[name], 22) if name in ("mega", "z") else None)

    def _toggle_phenomenon(self, name: str):
        self.selected_phenomenon = None if self.selected_phenomenon == name else name

    def _switch_buttons(self, x,y,forced=False,compact=False):
        team=self.battle.teams[0]; width=105 if compact else 236; height=46 if compact else 56
        for i,mon in enumerate(team.pokemon):
            if i==team.active or mon.fainted: continue
            col=i% (6 if compact else 3); row=0 if compact else i//3
            r=pygame.Rect(x+col*(width+7), y+row*(height+9), width, height)
            detail="" if compact else f"{'/'.join(t.upper() for t in mon.species.types)}  {mon.current_hp}/{max_hp(mon)}"
            self._button(r, mon.label, detail, SwitchAction(i), accent=TYPE_COLORS.get(mon.species.types[0],ACCENT), icon=self.sprites.pokemon_icon(mon.species.dex, 34 if compact else 46), font=self.small if compact else None)

    def _log_panel(self):
        r=pygame.Rect(852,76,404,658); self._panel(r)
        self._text("BATTLE LOG",(875,97),self.title)
        events=self.battle.events[-21:]
        y=140
        for event in events:
            color={"damage":TEXT,"faint":DANGER,"victory":HP,"turn":ACCENT,"move":(230,213,149),"status":(235,151,121)}.get(event.kind,MUTED)
            for line in self._wrap(event.text,45): self._text(line,(875,y),self.small,color); y+=25
        self._panel(pygame.Rect(871,650,365,63),PANEL2)
        self._text("AI DECISION",(882,658),self.small,ACCENT)
        for n,line in enumerate(self._wrap(self.last_ai_explanation,47)[:2]): self._text(line,(882,676+n*15),self.small,TEXT)

    def _analysis_panel(self):
        r=pygame.Rect(256,118,770,515); self._panel(r,(18,28,43)); pygame.draw.rect(self.screen,ACCENT,r,2,border_radius=8)
        self._text("LIVE ANALYSIS  •  public-information view",(282,142),self.title,ACCENT)
        p,o=self.battle.active(0),self.battle.active(1)
        for side,mon,x in [(0,p,284),(1,o,655)]:
            self._text(("YOU: " if side==0 else "FOE: ")+mon.label,(x,190),self.title)
            stats=all_stats(mon)
            lines=[f"Types: {' / '.join(mon.species.types).upper()}",f"HP: {mon.current_hp}/{stats['hp']}",f"Atk {stats['atk']}  Def {stats['def']}  SpA {stats['spa']}",f"SpD {stats['spd']}  Spe {stats['spe']}",f"Stages: {', '.join(f'{k} {v:+d}' for k,v in mon.stages.items() if v) or 'none'}"]
            for n,line in enumerate(lines):self._text(line,(x,230+n*32),self.font,TEXT if side==0 else MUTED)
        self._text("AI explanation (actual selected-action evaluation):",(284,424),self.font,ACCENT)
        for n,line in enumerate(self._wrap(self.last_ai_explanation,78)): self._text(line,(284,452+n*25),self.font)
        self._text("Press A to close. Hidden foe moves, item, ability and EVs remain hidden from AI analysis.",(284,586),self.small,MUTED)

    def _button(self, rect, label, detail, payload, accent=ACCENT, icon=None, font=None):
        mouse=pygame.mouse.get_pos(); hover=rect.collidepoint(mouse)
        pygame.draw.rect(self.screen,(44,65,91) if hover else PANEL2,rect,border_radius=8)
        pygame.draw.rect(self.screen,accent,rect,2,border_radius=8)
        tx = rect.x + 12
        if icon is not None:
            self.screen.blit(icon, icon.get_rect(midleft=(rect.x + 6, rect.centery))); tx = rect.x + 6 + icon.get_width() + 5
        label_font = font or self.font; room = rect.right - tx - 5
        ty = rect.y + 8 if (font is None or detail) else rect.centery - label_font.get_height() // 2
        self._text(self._fit_text(label, label_font, room), (tx, ty), label_font, TEXT)
        if detail:self._text(self._fit_text(detail, self.small, room),(tx,rect.y+29),self.small,MUTED)
        self.buttons.append((rect,payload))

    @staticmethod
    def _fit_text(text, font, max_width):
        """Shorten text with an ellipsis rather than letting it spill out of a button."""
        text = str(text)
        if font.size(text)[0] <= max_width: return text
        while len(text) > 1 and font.size(text + "…")[0] > max_width: text = text[:-1]
        return text + "…"

    def _panel(self,rect,color=PANEL): pygame.draw.rect(self.screen,color,rect,border_radius=10)
    def _chip(self,label,rect,type_name):
        pygame.draw.rect(self.screen,TYPE_COLORS.get(type_name,ACCENT),rect,border_radius=8); self._text(label,(rect.x+5,rect.y+4),self.small,(15,20,30))
    def _hp_bar(self,rect,current,maximum):
        pygame.draw.rect(self.screen,(63,73,91),rect,border_radius=5); ratio=max(0,min(1,current/max(1,maximum))); color=HP if ratio>.5 else ((235,185,74) if ratio>.2 else DANGER)
        pygame.draw.rect(self.screen,color,pygame.Rect(rect.x,rect.y,max(2,int(rect.w*ratio)),rect.h),border_radius=5)
    def _text(self,text,pos,font=None,color=TEXT): self.screen.blit((font or self.font).render(str(text),True,color),pos)
    def _wrap(self,text,width):
        words=text.split(); lines=[]; cur=""
        for w in words:
            if len(cur)+len(w)+1>width: lines.append(cur);cur=w
            else:cur=(cur+" "+w).strip()
        return lines+[cur] if cur else lines
    def _overlay(self,title,subtitle,color):
        shade=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA);shade.fill((4,7,13,190));self.screen.blit(shade,(0,0));self._text(title,(WIDTH//2-120,HEIGHT//2-42),self.big,color);self._text(subtitle,(WIDTH//2-175,HEIGHT//2+12),self.font,TEXT)
    def _starfield(self):
        for i in range(52):
            x=(i*173)%WIDTH;y=(i*97)%HEIGHT; pygame.draw.circle(self.screen,(35,49,75),(x,y),1)

def launch(): App().run()

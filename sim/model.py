"""
sim/model.py
The Mesa Model for Mabuhay Province (2020-2026).
Runs one of three scenarios: dynasty_dominant | competitive | reform.
"""

import csv as _csv
import logging
import random
from typing import Optional

from mesa import Model

from sim.world.state import GlobalFactors, SimClock, NATIONAL_EVENTS
from sim.world.locations import LOCATIONS
from sim.agents.base import BarangayAgent
from sim.agents.roles import ROLE_CLASS_MAP, ROLE_DISTRIBUTION
from sim.agents.names import random_name, assign_family_ids
from sim.agents.relationships import RelationshipGraph
from sim.inference.qwen_client import QwenClient, QwenConfig
from sim.db.logger import SimLogger

logger = logging.getLogger(__name__)

# Roles that sit in political offices (used for dynasty score + elections)
OFFICE_ROLES = ("governor", "vice_governor", "board_member",
                "mayor", "vice_mayor", "councilor", "barangay_captain")

# Roles that get Qwen inference every INFERENCE_INTERVAL ticks
POLITICAL_ROLES = (
    "governor", "vice_governor", "board_member",
    "mayor", "vice_mayor", "councilor", "barangay_captain",
    "contractor", "journalist", "auditor", "police",
)


class BarangayModel(Model):
    """
    One complete simulation environment for Mabuhay Province.
    Instantiate with scenario='dynasty_dominant', 'competitive', or 'reform'.

    dynasty_dominant : family holds all key offices, no restrictions
    competitive      : independent candidates, no family coordination
    reform           : anti-dynasty law active, stronger audit/media
    """

    INFERENCE_INTERVAL = 72    # every 3 sim-days (72 ticks)
    RELATIONSHIP_LOG_INTERVAL = 24

    VALID_SCENARIOS = ("dynasty_dominant", "competitive", "reform")

    def __init__(
        self,
        scenario: str = "dynasty_dominant",
        run_id: Optional[str] = None,
        qwen_config: Optional[QwenConfig] = None,
        output_dir: str = "output",
        seed: int = 42,
        agents_csv: Optional[str] = None,
    ):
        if scenario not in self.VALID_SCENARIOS:
            raise ValueError(f"scenario must be one of {self.VALID_SCENARIOS}")

        super().__init__()
        self.random = random.Random(seed)
        random.seed(seed)

        self.scenario = scenario
        self.dynasty_enabled = scenario == "dynasty_dominant"
        self.reform_active   = scenario == "reform"

        self.run_id    = run_id or f"mabuhay_{scenario}_{seed}"
        self.agents_csv = agents_csv

        # ── Core systems ─────────────────────────────────────────────
        self.clock          = SimClock()
        self.global_factors = GlobalFactors()
        self.locations      = LOCATIONS
        self.rel_graph      = RelationshipGraph()
        self.qwen           = QwenClient(qwen_config)
        self.db             = SimLogger(self.run_id, output_dir)

        self._tick_events: list = []

        # Apply scenario-specific starting conditions
        self._apply_scenario_init()

        # ── Spawn agents (Agent.__init__ registers with Mesa automatically) ──
        self._agents_list: list[BarangayAgent] = []
        if self.agents_csv:
            self._spawn_from_csv(self.agents_csv)
        else:
            self._spawn_agents()

        self.rel_graph.seed_family_bonds(self._agents_list, self.dynasty_enabled)
        self.rel_graph.seed_role_relationships(self._agents_list)
        self._update_dynasty_score()

        logger.info(
            f"BarangayModel ready: scenario={scenario}, "
            f"agents={len(self._agents_list)}, run_id={self.run_id}"
        )

    # ── Scenario init ─────────────────────────────────────────────────────

    def _apply_scenario_init(self):
        gf = self.global_factors
        if self.scenario == "dynasty_dominant":
            gf.audit_strength  = 0.30
            gf.media_presence  = 0.25
            gf.dynasty_score   = 0.60
            gf.corruption_index = 0.35
        elif self.scenario == "competitive":
            gf.audit_strength  = 0.50
            gf.media_presence  = 0.45
            gf.citizen_trust   = 0.55
        elif self.scenario == "reform":
            gf.audit_strength  = 0.65
            gf.media_presence  = 0.60
            gf.citizen_trust   = 0.62
            gf.institution_strength = 0.65

    # ── Agent spawning ────────────────────────────────────────────────────

    def _spawn_agents(self):
        agent_id = 0
        for role, count in ROLE_DISTRIBUTION.items():
            cls = ROLE_CLASS_MAP.get(role)
            if not cls:
                continue
            for _ in range(count):
                name  = random_name(role)
                agent = cls(
                    unique_id=agent_id,
                    model=self,
                    name=name,
                    dynasty_enabled=self.dynasty_enabled,
                )
                # Note: Agent.__init__ already calls model.register_agent()
                self._agents_list.append(agent)
                loc = self.locations.get(agent.HOME_ZONE)
                if loc:
                    loc.add_agent(agent.unique_id)
                agent_id += 1

        assign_family_ids(
            self._agents_list,
            num_families=3,
            dynasty_enabled=self.dynasty_enabled,
        )
        logger.info(f"Spawned {agent_id} agents")

    def _spawn_from_csv(self, csv_path: str):
        """
        Load agents from barangay_agents.csv (produced by agent_creation.py).
        Each row instantiates the correct role class, then demographic and
        economic attributes are overridden from the CSV so every run is
        reproducible against the same seed roster.
        """
        from sim.agents.base import Traits as AgentTraits

        def _parse_float(val, default=0.0):
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        def _parse_int(val, default=None):
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        agent_id = 0
        loaded = 0
        skipped = 0

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                role = row.get("role", "").strip()
                cls  = ROLE_CLASS_MAP.get(role)
                if not cls:
                    logger.warning(f"Unknown role '{role}' in CSV row {agent_id+1} — skipping")
                    skipped += 1
                    continue

                family_id = row.get("family_id", "").strip() or None

                agent = cls(
                    unique_id=agent_id,
                    model=self,
                    name=row.get("name", f"Agent_{agent_id}"),
                    family_id=family_id,
                    dynasty_enabled=self.dynasty_enabled,
                )

                # Override demographics
                agent.sex            = row.get("sex", "M").strip()
                agent.age            = _parse_int(row.get("age"))
                agent.education_level = _parse_int(row.get("education_level"))
                agent.social_class   = row.get("social_class", "").strip()
                agent.is_alive       = row.get("is_alive", "True").strip() == "True"
                agent.civil_degree   = _parse_int(row.get("civil_degree"))
                agent.relation_type  = row.get("relation_type", "").strip()
                agent.relation_label = row.get("relation_label", "").strip()

                # Override economic state
                agent.personal_wealth = _parse_float(row.get("wealth"), agent.personal_wealth)
                agent.income_per_day  = _parse_float(row.get("income_per_day"), agent.income_per_day)
                agent.satisfaction    = _parse_float(row.get("satisfaction"), agent.satisfaction)

                # Override traits from CSV columns
                agent.traits = AgentTraits(
                    integrity      = _parse_float(row.get("integrity"),      0.5),
                    greed          = _parse_float(row.get("greed"),          0.5),
                    ambition       = _parse_float(row.get("ambition"),       0.5),
                    family_loyalty = _parse_float(row.get("family_loyalty"), 0.5),
                    competence     = _parse_float(row.get("competence"),     0.5),
                    empathy        = _parse_float(row.get("empathy"),        0.5),
                )

                self._agents_list.append(agent)
                loc = self.locations.get(agent.HOME_ZONE)
                if loc:
                    loc.add_agent(agent.unique_id)
                agent_id += 1
                loaded += 1

        logger.info(f"Loaded {loaded} agents from {csv_path} ({skipped} rows skipped)")

    # ── Main step ─────────────────────────────────────────────────────────

    def step(self):
        """
        One tick = one in-game hour.
        1. Fire any pending national events
        2. Qwen inference batch (political agents, every INFERENCE_INTERVAL)
        3. Step all agents
        4. Co-location interactions
        5. Update global factors
        6. Log state
        7. Special events (elections, scandals, unrest)
        8. Advance clock
        """
        tick = self.clock.tick

        # 1. National events
        for event in self.clock.pending_national_events():
            self.global_factors.apply_national_event(event)
            self.log_event(None, "political", event.description)
            logger.info(f"[{self.run_id}] NATIONAL EVENT: {event.label}")

        # 2. Qwen inference
        if tick % self.INFERENCE_INTERVAL == 0:
            self._run_inference_batch()

        # 3. Step all agents
        for agent in list(self._agents_list):
            agent.step()

        # 4. Co-location interactions
        self._run_interactions()

        # 5. Global factors
        self.global_factors.natural_decay()
        self.global_factors.audit_suppression_from_dynasty()
        self.global_factors.pandemic_effects()
        self.global_factors.ofw_welfare_floor()
        self._update_dynasty_score()

        # 6. Logging
        self.db.log_global_state(self.clock, self.global_factors)
        if tick % 6 == 0:
            self.db.log_agent_states(tick, self._agents_list)
        for ev in self._tick_events:
            self.db.log_event(
                tick, self.clock.year, self.clock.day, self.clock.hour,
                ev["agent_id"], ev["agent_name"], ev["type"], ev["description"],
            )
        self._tick_events = []
        if tick % self.RELATIONSHIP_LOG_INTERVAL == 0:
            self.db.log_relationships(tick, self.rel_graph)
        if self.clock.hour == 23:
            self.db.flush_day(
                self.clock.year, self.clock.day,
                self.clock, self.global_factors,
                self._agents_list, self.rel_graph,
            )
        if tick % 240 == 0 and tick > 0:
            self.db.checkpoint(self.clock, self.global_factors, self._agents_list)

        # 7. Special events
        if self.clock.is_election_day:
            self._run_election()
        self._check_scandal_threshold()
        self._check_unrest_threshold()

        # 8. Advance clock
        self.clock.advance()

        if tick % 24 == 0:
            logger.info(
                f"[{self.run_id}] {self.clock.label} | "
                f"corruption={self.global_factors.corruption_index:.3f} "
                f"welfare={self.global_factors.welfare_index:.3f} "
                f"unrest={self.global_factors.unrest_level:.3f} "
                f"dynasty={self.global_factors.dynasty_score:.3f} "
                f"pandemic={self.global_factors.pandemic_severity:.2f}"
            )

    def run(self):
        logger.info(f"Starting simulation: {self.run_id}")
        try:
            while not self.clock.is_done:
                self.step()
        except KeyboardInterrupt:
            logger.info("Simulation interrupted")
        finally:
            self.db.close()
        logger.info(f"Simulation complete: {self.run_id}")

    # ── Inference ─────────────────────────────────────────────────────────

    def _run_inference_batch(self):
        from sim.agents.roles import (
            Governor, ViceGovernor, ProvincialBoardMember,
            Mayor, ViceMayor, Councilor, BarangayCaptain,
            Contractor, Journalist, Auditor, PoliceOfficer,
        )
        political = (Governor, ViceGovernor, ProvincialBoardMember,
                     Mayor, ViceMayor, Councilor, BarangayCaptain,
                     Contractor, Journalist, Auditor, PoliceOfficer)

        batch = [a for a in self._agents_list if isinstance(a, political)]
        triggered = [
            a for a in self._agents_list
            if not isinstance(a, political) and
            (a.satisfaction < 30 or a.needs_inference)
        ]
        batch.extend(triggered[:20])

        if not batch:
            return

        world_state = {**self.global_factors.to_dict(), **self.clock.to_dict()}
        decisions   = self.qwen.decide_batch(batch, world_state)

        for agent in batch:
            action = decisions.get(agent.unique_id)
            if action:
                agent.pending_action = action
                if action.get("corruption"):
                    declared = action.get("declared_budget", 0) or 0
                    actual   = action.get("actual_budget", declared) or declared
                    self.db.log_corruption_act(
                        self.clock.tick, agent.unique_id, agent.name,
                        action["action_id"], declared, actual,
                    )
            agent.needs_inference = False

    # ── Interactions ──────────────────────────────────────────────────────

    def _run_interactions(self):
        active_locs = [
            k for k, loc in self.locations.items()
            if (len(loc.current_agents) >= 2 and
                (loc.zone_type not in ("residential",) or
                 self.clock.hour in range(8, 22)))
        ]
        for loc_key in active_locs:
            loc = self.locations[loc_key]
            if len(loc.current_agents) < 2:
                continue
            present = loc.current_agents[:20]
            for _ in range(min(3, len(present) // 2)):
                if len(present) < 2:
                    break
                a_id, b_id = random.sample(present, 2)
                self._interact_pair(a_id, b_id)

    def _interact_pair(self, a_id: int, b_id: int):
        agent_map = {a.unique_id: a for a in self._agents_list}
        a = agent_map.get(a_id)
        b = agent_map.get(b_id)
        if not a or not b:
            return
        from sim.agents.roles import (
            Governor, ViceGovernor, ProvincialBoardMember,
            Mayor, ViceMayor, Councilor, Contractor, Journalist,
        )
        political = (Governor, ViceGovernor, ProvincialBoardMember,
                     Mayor, ViceMayor, Councilor, Contractor, Journalist)

        if isinstance(a, political) and isinstance(b, political):
            trust_ab = self.rel_graph.get_trust(a_id, b_id)
            outcome  = "positive" if trust_ab > 0.5 else ("negative" if trust_ab < -0.2 else "neutral")
            self.rel_graph.interact(a_id, b_id, outcome)
            self.rel_graph.interact(b_id, a_id, outcome)
            if (self.dynasty_enabled and
                    getattr(a, "family_id", None) and
                    getattr(a, "family_id", None) == getattr(b, "family_id", None)):
                self.rel_graph.cover_for(a_id, b_id)
        else:
            avg_sat = (a.satisfaction + b.satisfaction) / 2
            a.satisfaction = a.satisfaction * 0.95 + avg_sat * 0.05
            b.satisfaction = b.satisfaction * 0.95 + avg_sat * 0.05

    # ── Election ──────────────────────────────────────────────────────────

    def _run_election(self):
        from sim.agents.roles import Governor, Mayor, Councilor, ProvincialBoardMember

        yr = self.clock.calendar_year
        logger.info(f"[{self.run_id}] ELECTION {yr} at {self.clock.label}")
        self.log_event(None, "political", f"Election day {yr} — votes being cast")

        candidates = [
            a for a in self._agents_list
            if isinstance(a, (Governor, Mayor, Councilor, ProvincialBoardMember))
        ]

        for candidate in candidates:
            # Reform scenario: strict anti-dynasty disqualification
            if self.reform_active and candidate.family_id:
                relative_in_office = any(
                    a.family_id == candidate.family_id and
                    a is not candidate and
                    a.ROLE in OFFICE_ROLES
                    for a in self._agents_list
                )
                if relative_in_office:
                    logger.info(f"  {candidate.name} disqualified (reform law)")
                    self.log_event(candidate, "political",
                        f"{candidate.name} disqualified — Anti-Dynasty Act")
                    continue

            avg_trust  = self.rel_graph.influence_score(candidate.unique_id)
            avg_sat    = sum(a.satisfaction for a in self._agents_list) / max(1, len(self._agents_list))
            name_bonus = 0.15 if self.dynasty_enabled and candidate.family_id else 0.0
            # Competitive scenario: incumbents get slight penalty
            inc_pen    = -0.10 if self.scenario == "competitive" and candidate.family_id else 0.0
            vote_score = (avg_trust * 0.4 + avg_sat / 100 * 0.4 +
                          candidate.traits.competence * 0.2 + name_bonus + inc_pen)
            logger.info(f"  {candidate.name} ({candidate.ROLE}): {vote_score:.3f}")

        self.log_event(None, "political", f"Election complete — {yr}")

    # ── Scandal & unrest ──────────────────────────────────────────────────

    def _check_scandal_threshold(self):
        gf = self.global_factors
        if (gf.corruption_index > 0.55 and
                gf.media_presence > 0.35 and
                random.random() < 0.005):
            from sim.agents.roles import Governor, Mayor, ViceMayor, Councilor, Contractor
            political = [a for a in self._agents_list
                         if isinstance(a, (Governor, Mayor, ViceMayor, Councilor, Contractor))]
            if not political:
                return
            culprit  = max(political, key=lambda a: a.corrupt_acts)
            severity = gf.corruption_index * gf.media_presence
            gf.citizen_trust  = max(0, gf.citizen_trust  - severity * 0.15)
            gf.unrest_level   = min(1, gf.unrest_level   + severity * 0.10)
            gf.dynasty_score  = max(0, gf.dynasty_score  - severity * 0.05)
            gf.media_presence = min(1, gf.media_presence + 0.03)
            self.rel_graph.scandal_hit(
                culprit.unique_id,
                [a.unique_id for a in self._agents_list],
                severity=severity,
            )
            msg = f"SCANDAL: {culprit.name} exposed for corruption (severity={severity:.2f})"
            logger.warning(f"[{self.run_id}] {msg}")
            self.log_event(culprit, "crime", msg)

    def _check_unrest_threshold(self):
        gf = self.global_factors
        if gf.unrest_level >= 1.0:
            msg = "UNREST PEAK — recall event triggered"
            logger.warning(f"[{self.run_id}] {msg}")
            self.log_event(None, "political", msg)
            gf.unrest_level  = 0.4
            gf.dynasty_score = max(0, gf.dynasty_score - 0.2)
            gf.citizen_trust = min(1, gf.citizen_trust + 0.05)

    # ── Helpers ───────────────────────────────────────────────────────────

    def log_event(self, agent: Optional[BarangayAgent], event_type: str, description: str):
        self._tick_events.append({
            "agent_id":    agent.unique_id if agent else -1,
            "agent_name":  agent.name      if agent else "SYSTEM",
            "type":        event_type,
            "description": description,
        })

    def _update_dynasty_score(self):
        office_holders = [a for a in self._agents_list if a.ROLE in OFFICE_ROLES]
        self.global_factors.update_dynasty_score(office_holders)

    @property
    def agents(self) -> list:
        return self._agents_list

    def get_agent_by_id(self, agent_id: int) -> Optional[BarangayAgent]:
        return next((a for a in self._agents_list if a.unique_id == agent_id), None)

    def summary(self) -> dict:
        return {
            "run_id":          self.run_id,
            "scenario":        self.scenario,
            "clock":           self.clock.to_dict(),
            "global_factors":  self.global_factors.to_dict(),
            "agent_count":     len(self._agents_list),
            "relationships":   self.rel_graph.summary(),
        }

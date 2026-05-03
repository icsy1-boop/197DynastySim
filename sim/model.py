"""
sim/model.py
The Mesa Model — owns the scheduler, all agents, global state,
the relationship graph, the Qwen client, and the logger.
This is the single entry point for running one environment.
"""

import logging
import random
from typing import Optional

from mesa import Model

from sim.world.state import GlobalFactors, SimClock
from sim.world.locations import LOCATIONS
from sim.agents.base import BarangayAgent
from sim.agents.roles import ROLE_CLASS_MAP, ROLE_DISTRIBUTION
from sim.agents.names import random_name, assign_family_ids
from sim.agents.relationships import RelationshipGraph
from sim.inference.qwen_client import QwenClient, QwenConfig
from sim.db.logger import SimLogger

logger = logging.getLogger(__name__)


class BarangayModel(Model):
    """
    One complete simulation environment.
    Instantiate twice — once with dynasty_enabled=True, once False —
    to run the comparative experiment.
    """

    # How often (in ticks) to run inference on political agents
    INFERENCE_INTERVAL = 4    # every 4 hours of sim time

    # How often to log relationships (daily = every 24 ticks)
    RELATIONSHIP_LOG_INTERVAL = 24

    def __init__(
        self,
        dynasty_enabled: bool = True,
        run_id: Optional[str] = None,
        qwen_config: Optional[QwenConfig] = None,
        output_dir: str = "output",
        seed: int = 42,
    ):
        super().__init__()
        self.random = random.Random(seed)
        random.seed(seed)

        self.dynasty_enabled = dynasty_enabled
        label = "dynasty" if dynasty_enabled else "no_dynasty"
        self.run_id = run_id or f"barangay_{label}_{seed}"

        # ── Core systems ──────────────────────────────────────────────
        self.clock         = SimClock()
        self.global_factors = GlobalFactors()
        self.locations     = LOCATIONS
        self.rel_graph     = RelationshipGraph()
        self.qwen          = QwenClient(qwen_config)
        self.db            = SimLogger(self.run_id, output_dir)

        # ── Event buffer for this tick ─────────────────────────────────
        self._tick_events: list = []

        # ── Spawn all agents ──────────────────────────────────────────
        self._agents_list: list[BarangayAgent] = []
        self._spawn_agents()

        # ── Seed relationships ─────────────────────────────────────────
        self.rel_graph.seed_family_bonds(self._agents_list, dynasty_enabled)
        self.rel_graph.seed_role_relationships(self._agents_list)

        # ── Initial dynasty score ─────────────────────────────────────
        self._update_dynasty_score()

        logger.info(
            f"BarangayModel initialized: dynasty={dynasty_enabled}, "
            f"agents={len(self._agents_list)}, run_id={self.run_id}"
        )

    # ── Agent spawning ────────────────────────────────────────────────────

    def _spawn_agents(self):
        agent_id = 0
        for role, count in ROLE_DISTRIBUTION.items():
            cls = ROLE_CLASS_MAP.get(role)
            if not cls:
                continue
            for _ in range(count):
                name = random_name(role)
                agent = cls(
                    unique_id=agent_id,
                    model=self,
                    name=name,
                    dynasty_enabled=self.dynasty_enabled,
                )
                self.register_agent(agent)
                self._agents_list.append(agent)
                # Place agent in their home location
                loc = self.locations.get(agent.HOME_ZONE)
                if loc:
                    loc.add_agent(agent_id)
                agent_id += 1

        # Assign family IDs to political agents (dynasty env only)
        assign_family_ids(
            self._agents_list,
            num_families=3,
            dynasty_enabled=self.dynasty_enabled,
        )

        logger.info(f"Spawned {agent_id} agents")

    # ── Main step ─────────────────────────────────────────────────────────

    def step(self):
        """
        One tick = one in-game hour.
        Order:
          1. Run Qwen inference for agents that need a decision
          2. Step all agents (Mesa scheduler)
          3. Run interactions between co-located agents
          4. Update global factors
          5. Log state
          6. Handle special events (elections, scandals)
          7. Advance clock
        """
        tick = self.clock.tick

        # 1. Qwen inference batch (political + triggered citizens)
        if tick % self.INFERENCE_INTERVAL == 0:
            self._run_inference_batch()

        # 2. Step all agents (shuffled for fairness)
        for agent in list(self._agents_list):
            agent.step()

        # 3. Co-location interactions
        self._run_interactions()

        # 4. Global factor updates
        self.global_factors.natural_decay()
        self.global_factors.audit_suppression_from_dynasty()
        self._update_dynasty_score()

        # 5. Logging
        self.db.log_global_state(self.clock, self.global_factors)

        # Log agent states every 6 ticks (every 6 sim-hours) to keep DB lean
        if tick % 6 == 0:
            self.db.log_agent_states(tick, self._agents_list)

        # Flush event queue to DB
        for ev in self._tick_events:
            self.db.log_event(
                tick, self.clock.year, self.clock.day, self.clock.hour,
                ev["agent_id"], ev["agent_name"], ev["type"], ev["description"]
            )
        self._tick_events = []

        # Log relationships daily
        if tick % self.RELATIONSHIP_LOG_INTERVAL == 0:
            self.db.log_relationships(tick, self.rel_graph)

        # Day boundary
        if self.clock.hour == 23:
            self.db.flush_day(
                self.clock.year, self.clock.day,
                self.clock, self.global_factors,
                self._agents_list, self.rel_graph,
            )

        # Checkpoint every 10 sim-days
        if tick % 240 == 0 and tick > 0:
            self.db.checkpoint(self.clock, self.global_factors, self._agents_list)

        # 6. Special events
        if self.clock.is_election_day:
            self._run_election()

        self._check_scandal_threshold()
        self._check_unrest_threshold()

        # 7. Advance clock
        self.clock.advance()

        if tick % 24 == 0:
            logger.info(
                f"[{self.run_id}] {self.clock.label} | "
                f"corruption={self.global_factors.corruption_index:.3f} "
                f"welfare={self.global_factors.welfare_index:.3f} "
                f"unrest={self.global_factors.unrest_level:.3f} "
                f"dynasty={self.global_factors.dynasty_score:.3f}"
            )

    def run(self):
        """Run the full simulation until clock.is_done."""
        logger.info(f"Starting simulation: {self.run_id}")
        try:
            while not self.clock.is_done:
                self.step()
        except KeyboardInterrupt:
            logger.info("Simulation interrupted by user")
        logger.info(f"Simulation complete: {self.run_id}")

    # ── Inference ─────────────────────────────────────────────────────────

    def _run_inference_batch(self):
        """
        Collect agents that need a Qwen decision this tick.
        Political agents run every INFERENCE_INTERVAL ticks.
        Citizens run only when triggered (satisfaction low, major event, etc.)
        """
        from sim.agents.roles import (Mayor, ViceMayor, Councilor,
                                       BarangayCaptain, Contractor,
                                       Journalist, Auditor, PoliceOfficer)

        political_roles = (Mayor, ViceMayor, Councilor, BarangayCaptain,
                           Contractor, Journalist, Auditor, PoliceOfficer)

        batch = [
            a for a in self._agents_list
            if isinstance(a, political_roles)
        ]

        # Add triggered citizens (satisfaction very low or major event nearby)
        triggered = [
            a for a in self._agents_list
            if not isinstance(a, political_roles)
            and (a.satisfaction < 30 or a.needs_inference)
        ]
        batch.extend(triggered[:20])   # cap to avoid huge batches

        if not batch:
            return

        world_state = {**self.global_factors.to_dict(), **self.clock.to_dict()}
        decisions = self.qwen.decide_batch(batch, world_state)

        for agent in batch:
            action = decisions.get(agent.unique_id)
            if action:
                agent.pending_action = action
                # Log corruption acts immediately for tracking
                if action.get("corruption"):
                    declared = action.get("declared_budget", 0) or 0
                    actual   = action.get("actual_budget", declared) or declared
                    self.db.log_corruption_act(
                        self.clock.tick,
                        agent.unique_id, agent.name,
                        action["action_id"],
                        declared, actual,
                    )
            agent.needs_inference = False

    # ── Interactions ──────────────────────────────────────────────────────

    def _run_interactions(self):
        """
        For each location, pair up co-located agents for interaction.
        Only run for non-trivial locations (not residential zones during sleep).
        """
        active_locs = [
            k for k, loc in self.locations.items()
            if (len(loc.current_agents) >= 2 and
                loc.zone_type not in ("residential",) or
                self.clock.hour in range(8, 22))
        ]

        for loc_key in active_locs:
            loc = self.locations[loc_key]
            if len(loc.current_agents) < 2:
                continue

            # Sample up to 3 pairs per location per tick
            present = loc.current_agents[:20]   # cap for performance
            pairs_to_run = min(3, len(present) // 2)

            for _ in range(pairs_to_run):
                if len(present) < 2:
                    break
                a_id, b_id = random.sample(present, 2)
                self._interact_pair(a_id, b_id)

    def _interact_pair(self, a_id: int, b_id: int):
        """
        Run a single interaction between two agents.
        Uses Qwen if both are political, rule-based otherwise.
        """
        agent_map = {a.unique_id: a for a in self._agents_list}
        a = agent_map.get(a_id)
        b = agent_map.get(b_id)
        if not a or not b:
            return

        from sim.agents.roles import (Mayor, ViceMayor, Councilor,
                                       Contractor, Journalist)
        political = (Mayor, ViceMayor, Councilor, Contractor, Journalist)

        if isinstance(a, political) and isinstance(b, political):
            # Qwen interaction (single call, batched in next cycle)
            # For now: rule-based with relationship influence
            trust_a_b = self.rel_graph.get_trust(a_id, b_id)
            if trust_a_b > 0.5:
                outcome = "positive"
            elif trust_a_b < -0.2:
                outcome = "negative"
            else:
                outcome = "neutral"
            new_trust = self.rel_graph.interact(a_id, b_id, outcome)
            self.rel_graph.interact(b_id, a_id, outcome)   # asymmetric update

            # Family cover mechanic — dynasty only
            if (self.dynasty_enabled and
                    getattr(a, "family_id", None) and
                    getattr(a, "family_id", None) == getattr(b, "family_id", None)):
                self.rel_graph.cover_for(a_id, b_id)
        else:
            # Citizen interaction: simple satisfaction exchange
            avg_sat = (a.satisfaction + b.satisfaction) / 2
            a.satisfaction = a.satisfaction * 0.95 + avg_sat * 0.05
            b.satisfaction = b.satisfaction * 0.95 + avg_sat * 0.05

    # ── Election ──────────────────────────────────────────────────────────

    def _run_election(self):
        """
        Simple election: vote probability per candidate based on
        trust network + citizen satisfaction.
        Dynasty env: incumbents get name-recognition bonus.
        Non-dynasty env: if incumbent has family member in office → disqualified.
        """
        from sim.agents.roles import Mayor, Councilor

        logger.info(f"[{self.run_id}] ELECTION at {self.clock.label}")
        self.log_event(None, "political", "Election day — votes being cast")

        candidates = [a for a in self._agents_list
                      if isinstance(a, (Mayor, Councilor))]

        for candidate in candidates:
            # Anti-dynasty check
            if not self.dynasty_enabled and candidate.family_id:
                other_family_in_office = any(
                    a.family_id == candidate.family_id and a is not candidate
                    for a in candidates
                )
                if other_family_in_office:
                    logger.info(
                        f"  {candidate.name} disqualified by anti-dynasty rule"
                    )
                    self.log_event(candidate, "political",
                        f"{candidate.name} disqualified — anti-dynasty bill")
                    continue

            # Vote score: trust from citizens + satisfaction average
            avg_trust    = self.rel_graph.influence_score(candidate.unique_id)
            avg_sat      = sum(a.satisfaction for a in self._agents_list) / max(1, len(self._agents_list))
            name_bonus   = 0.15 if (self.dynasty_enabled and candidate.family_id) else 0.0
            vote_score   = (avg_trust * 0.4 + avg_sat / 100 * 0.4 +
                            candidate.traits.competence * 0.2 + name_bonus)

            logger.info(f"  {candidate.name}: vote_score={vote_score:.3f}")

        self.log_event(None, "political",
            f"Election complete — Year {self.clock.year}")

    # ── Scandal detection ─────────────────────────────────────────────────

    def _check_scandal_threshold(self):
        """
        If corruption_index spikes and media_presence is high enough,
        trigger a scandal event that damages trust and dynasty score.
        """
        gf = self.global_factors
        if (gf.corruption_index > 0.55 and
                gf.media_presence > 0.35 and
                random.random() < 0.005):

            # Find most corrupt political agent
            from sim.agents.roles import Mayor, ViceMayor, Councilor, Contractor
            political = [a for a in self._agents_list
                         if isinstance(a, (Mayor, ViceMayor, Councilor, Contractor))]
            if not political:
                return
            culprit = max(political, key=lambda a: a.corrupt_acts)

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

            msg = (f"SCANDAL: {culprit.name} exposed for corruption "
                   f"(severity={severity:.2f})")
            logger.warning(f"[{self.run_id}] {msg}")
            self.log_event(culprit, "crime", msg)

    # ── Unrest threshold ──────────────────────────────────────────────────

    def _check_unrest_threshold(self):
        gf = self.global_factors
        if gf.unrest_level >= 1.0:
            msg = "UNREST PEAK — recall event triggered"
            logger.warning(f"[{self.run_id}] {msg}")
            self.log_event(None, "political", msg)
            # Reset unrest partially, damage dynasty score
            gf.unrest_level  = 0.4
            gf.dynasty_score = max(0, gf.dynasty_score - 0.2)
            gf.citizen_trust = min(1, gf.citizen_trust + 0.05)

    # ── Helpers ───────────────────────────────────────────────────────────

    def log_event(self, agent: Optional[BarangayAgent],
                  event_type: str, description: str):
        """Queue an event for this tick's log flush."""
        self._tick_events.append({
            "agent_id":   agent.unique_id if agent else -1,
            "agent_name": agent.name      if agent else "SYSTEM",
            "type":       event_type,
            "description": description,
        })

    def _update_dynasty_score(self):
        office_holders = [
            a for a in self._agents_list
            if a.ROLE in ("mayor", "vice_mayor", "councilor", "barangay_captain")
        ]
        self.global_factors.update_dynasty_score(office_holders)

    @property
    def agents(self) -> list:
        return self._agents_list

    def get_agent_by_id(self, agent_id: int) -> Optional[BarangayAgent]:
        return next((a for a in self._agents_list
                     if a.unique_id == agent_id), None)

    def summary(self) -> dict:
        return {
            "run_id":          self.run_id,
            "dynasty_enabled": self.dynasty_enabled,
            "clock":           self.clock.to_dict(),
            "global_factors":  self.global_factors.to_dict(),
            "agent_count":     len(self._agents_list),
            "relationships":   self.rel_graph.summary(),
        }

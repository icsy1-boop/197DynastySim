"""
agents/relationships.py
Asymmetric trust network using NetworkX DiGraph.
Edge weight = trust score in [-1, 1].
  -1  = deep distrust / rival
   0  = neutral stranger
  +1  = close ally / family
"""

import random
import networkx as nx
from typing import Optional, List, Tuple


class RelationshipGraph:
    """
    Wraps a NetworkX DiGraph where each directed edge (A→B)
    has a 'trust' attribute representing how much A trusts B.
    Stored separately from agents so the graph can be queried
    and serialized independently.
    """

    def __init__(self):
        self.G = nx.DiGraph()

    # ── Node management ──────────────────────────────────────────────────

    def add_agent(self, agent_id: int, role: str, family_id: Optional[str] = None):
        self.G.add_node(agent_id, role=role, family_id=family_id)

    def remove_agent(self, agent_id: int):
        if self.G.has_node(agent_id):
            self.G.remove_node(agent_id)

    # ── Edge management ──────────────────────────────────────────────────

    def set_trust(self, from_id: int, to_id: int, trust: float):
        trust = max(-1.0, min(1.0, trust))
        if self.G.has_edge(from_id, to_id):
            self.G[from_id][to_id]["trust"] = trust
        else:
            self.G.add_edge(from_id, to_id, trust=trust)

    def get_trust(self, from_id: int, to_id: int) -> float:
        if self.G.has_edge(from_id, to_id):
            return self.G[from_id][to_id]["trust"]
        return 0.0   # strangers are neutral

    def update_trust(self, from_id: int, to_id: int, delta: float):
        current = self.get_trust(from_id, to_id)
        self.set_trust(from_id, to_id, current + delta)

    # ── Seeding ──────────────────────────────────────────────────────────

    def seed_family_bonds(self, agents: list, dynasty_enabled: bool):
        """
        Pre-populate edges for agents sharing a family_id.
        Dynasty environment: family bonds start high (0.8–1.0).
        Non-dynasty environment: family bonds still exist socially
        but are weaker (0.4–0.6) since no political advantage.
        """
        for a in agents:
            self.add_agent(a.unique_id, a.ROLE,
                           getattr(a, "family_id", None))

        # Build family groups
        family_map: dict[str, list] = {}
        for a in agents:
            fid = getattr(a, "family_id", None)
            if fid:
                family_map.setdefault(fid, []).append(a.unique_id)

        for fid, members in family_map.items():
            for i in members:
                for j in members:
                    if i != j:
                        trust = random.uniform(0.75, 1.0) if dynasty_enabled \
                                else random.uniform(0.35, 0.60)
                        self.set_trust(i, j, trust)

        # Random weak ties between all other agents (sparse)
        all_ids = [a.unique_id for a in agents]
        for _ in range(len(all_ids) * 2):
            a, b = random.sample(all_ids, 2)
            if not self.G.has_edge(a, b):
                self.set_trust(a, b, random.uniform(-0.1, 0.2))

    def seed_role_relationships(self, agents: list):
        """
        Political agents start with role-based biases:
        Contractor ↔ Politician: slight positive (mutually useful)
        Journalist ↔ Politician: slight negative (watchdog tension)
        Auditor ↔ Contractor:    slight negative
        """
        from .roles import Mayor, ViceMayor, Councilor, Contractor, Journalist, Auditor

        for a in agents:
            for b in agents:
                if a is b: continue
                if self.G.has_edge(a.unique_id, b.unique_id): continue

                trust = 0.0
                if isinstance(a, (Mayor, ViceMayor, Councilor)) and isinstance(b, Contractor):
                    trust = random.uniform(0.1, 0.35)
                elif isinstance(a, Journalist) and isinstance(b, (Mayor, ViceMayor, Councilor)):
                    trust = random.uniform(-0.2, 0.05)
                elif isinstance(a, Auditor) and isinstance(b, Contractor):
                    trust = random.uniform(-0.25, 0.0)

                if trust != 0.0:
                    self.set_trust(a.unique_id, b.unique_id, trust)

    # ── Interaction ─────────────────────────────────────────────────────

    def interact(self, from_id: int, to_id: int,
                 outcome: str = "neutral") -> float:
        """
        Process a single interaction between two agents.
        outcome: 'positive' | 'negative' | 'betrayal' | 'neutral'
        Returns the new trust value.
        """
        deltas = {
            "positive":  random.uniform(0.02, 0.08),
            "negative":  random.uniform(-0.06, -0.02),
            "betrayal":  random.uniform(-0.20, -0.10),
            "neutral":   random.uniform(-0.01, 0.02),
        }
        delta = deltas.get(outcome, 0.0)
        self.update_trust(from_id, to_id, delta)
        return self.get_trust(from_id, to_id)

    def cover_for(self, cover_er_id: int, covered_id: int):
        """
        A covers for B's corrupt act — trust goes up between them,
        but if discovered later both take a hit.
        """
        self.update_trust(cover_er_id, covered_id,  0.05)
        self.update_trust(covered_id,  cover_er_id, 0.03)

    def scandal_hit(self, corrupt_agent_id: int, all_agent_ids: List[int],
                    severity: float = 0.3):
        """
        Scandal breaks: all agents trust the corrupt agent less.
        Severity in [0,1].
        """
        for aid in all_agent_ids:
            if aid != corrupt_agent_id:
                self.update_trust(aid, corrupt_agent_id,
                                  -severity * random.uniform(0.1, 0.4))

    # ── Queries ──────────────────────────────────────────────────────────

    def allies_of(self, agent_id: int, threshold: float = 0.4) -> List[int]:
        return [
            b for _, b, d in self.G.out_edges(agent_id, data=True)
            if d.get("trust", 0) >= threshold
        ]

    def rivals_of(self, agent_id: int, threshold: float = -0.2) -> List[int]:
        return [
            b for _, b, d in self.G.out_edges(agent_id, data=True)
            if d.get("trust", 0) <= threshold
        ]

    def most_trusted_by(self, agent_id: int) -> Optional[int]:
        edges = list(self.G.out_edges(agent_id, data=True))
        if not edges: return None
        return max(edges, key=lambda e: e[2].get("trust", 0))[1]

    def family_coverage_probability(self, agent_a_id: int,
                                    agent_b_id: int) -> float:
        """
        Probability that B covers for A given their trust.
        Higher trust = more likely to look the other way.
        """
        trust = self.get_trust(agent_b_id, agent_a_id)
        return max(0.0, trust)  # trust is already [0,1] for positives

    def influence_score(self, agent_id: int) -> float:
        """
        Simple centrality-based influence: how trusted this agent is
        on average by everyone who has an opinion of them.
        """
        in_edges = list(self.G.in_edges(agent_id, data=True))
        if not in_edges: return 0.0
        return sum(d.get("trust", 0) for _, _, d in in_edges) / len(in_edges)

    # ── Serialization ───────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {"id": n, **self.G.nodes[n]}
                for n in self.G.nodes
            ],
            "edges": [
                {"from": u, "to": v, "trust": round(d.get("trust", 0), 3)}
                for u, v, d in self.G.edges(data=True)
            ],
        }

    def summary(self) -> dict:
        trusts = [d.get("trust", 0) for _, _, d in self.G.edges(data=True)]
        return {
            "num_nodes":    self.G.number_of_nodes(),
            "num_edges":    self.G.number_of_edges(),
            "avg_trust":    round(sum(trusts) / len(trusts), 3) if trusts else 0,
            "density":      round(nx.density(self.G), 4),
        }

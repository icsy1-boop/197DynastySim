"""
world/state.py
Global factors for Barangay Mabuhay.
All values are floats on [0, 1] unless noted.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class GlobalFactors:
    institution_strength: float = 0.55
    corruption_index: float = 0.20       # aggregate, computed from agent acts
    welfare_index: float = 0.60          # composite: health + edu + employment
    audit_strength: float = 0.45
    media_presence: float = 0.40
    city_budget: float = 1_000_000.0     # Philippine pesos, absolute
    citizen_trust: float = 0.55
    unrest_level: float = 0.10           # 0-1; at 1.0 triggers recall event
    dynasty_score: float = 0.00          # computed from office share

    def update_dynasty_score(self, office_holders: list):
        """Fraction of offices held by the dominant family."""
        if not office_holders:
            return
        from collections import Counter
        fam_counts = Counter(a.family_id for a in office_holders if a.family_id)
        if not fam_counts:
            self.dynasty_score = 0.0
            return
        top = fam_counts.most_common(1)[0][1]
        self.dynasty_score = top / len(office_holders)

    def apply_corruption_effects(self, corruption_delta: float):
        """Called each tick after agent actions resolve."""
        self.corruption_index = clamp(self.corruption_index + corruption_delta)
        # Corruption erodes trust and welfare
        self.citizen_trust   = clamp(self.citizen_trust   - corruption_delta * 0.4)
        self.welfare_index   = clamp(self.welfare_index   - corruption_delta * 0.2)
        self.unrest_level    = clamp(self.unrest_level    + corruption_delta * 0.3)

    def apply_honest_service(self, service_delta: float):
        self.welfare_index   = clamp(self.welfare_index   + service_delta * 0.5)
        self.citizen_trust   = clamp(self.citizen_trust   + service_delta * 0.3)
        self.unrest_level    = clamp(self.unrest_level    - service_delta * 0.2)

    def natural_decay(self):
        """Welfare decays each day without active maintenance."""
        decay = 0.001 * (1 - self.institution_strength)
        self.welfare_index = clamp(self.welfare_index - decay)

    def audit_suppression_from_dynasty(self):
        """High dynasty score weakens audit strength."""
        self.audit_strength = clamp(
            self.audit_strength - self.dynasty_score * 0.005
        )

    def to_dict(self) -> dict:
        return {
            "institution_strength": round(self.institution_strength, 4),
            "corruption_index":     round(self.corruption_index, 4),
            "welfare_index":        round(self.welfare_index, 4),
            "audit_strength":       round(self.audit_strength, 4),
            "media_presence":       round(self.media_presence, 4),
            "city_budget":          round(self.city_budget, 2),
            "citizen_trust":        round(self.citizen_trust, 4),
            "unrest_level":         round(self.unrest_level, 4),
            "dynasty_score":        round(self.dynasty_score, 4),
        }


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass
class SimClock:
    """
    Tracks simulation time.
    1 tick = 1 in-game hour.
    """
    tick: int = 0          # absolute ticks since start
    hour: int = 6          # 0-23
    day: int = 1           # 1-365
    year: int = 1          # 1-6 (6-year sim)

    MAX_YEARS: int = 6

    def advance(self):
        self.tick += 1
        self.hour += 1
        if self.hour >= 24:
            self.hour = 0
            self.day += 1
            if self.day > 365:
                self.day = 1
                self.year += 1

    @property
    def is_election_day(self) -> bool:
        # Elections every 3 years, on day 180
        return self.day == 180 and self.year in (3, 6)

    @property
    def is_done(self) -> bool:
        return self.year > self.MAX_YEARS

    @property
    def label(self) -> str:
        return f"Y{self.year} D{self.day} {self.hour:02d}:00"

    def to_dict(self) -> dict:
        return {"tick": self.tick, "hour": self.hour,
                "day": self.day, "year": self.year}

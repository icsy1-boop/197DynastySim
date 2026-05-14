"""
world/state.py
Global factors for Mabuhay Province simulation (2020-2026).
"""

from dataclasses import dataclass
from typing import List


@dataclass
class NationalEvent:
    calendar_year: int
    day: int          # 1-365
    label: str
    description: str
    effects: dict     # GlobalFactors field_name -> delta


NATIONAL_EVENTS: List[NationalEvent] = [
    NationalEvent(2020, 60, "COVID_Onset",
        "COVID-19 first cases confirmed in Mabuhay Province",
        {"pandemic_severity": +0.40, "welfare_index": -0.08, "unrest_level": +0.05}),
    NationalEvent(2020, 83, "ECQ_Declared",
        "Enhanced Community Quarantine declared — lockdown begins",
        {"pandemic_severity": +0.40, "welfare_index": -0.15, "city_budget": -300_000,
         "unrest_level": +0.12, "citizen_trust": -0.06}),
    NationalEvent(2021, 60, "Second_Wave",
        "COVID second wave — Delta variant hits the province",
        {"pandemic_severity": +0.20, "welfare_index": -0.05, "unrest_level": +0.08}),
    NationalEvent(2021, 200, "Vaccine_Rollout",
        "Vaccine rollout — slow distribution to province",
        {"pandemic_severity": -0.15, "citizen_trust": +0.04}),
    NationalEvent(2022, 90, "Pre_Election_Spending",
        "Vote-buying season — cash and goods distributed",
        {"corruption_index": +0.05, "dynasty_score": +0.03, "unrest_level": +0.03}),
    NationalEvent(2022, 135, "National_Elections",
        "2022 elections — Marcos Jr. wins; local dynasties ride national wave",
        {"dynasty_score": +0.08, "citizen_trust": -0.06, "audit_strength": -0.05,
         "pandemic_severity": -0.30}),
    NationalEvent(2022, 200, "COVID_Downgraded",
        "COVID downgraded to alert level 1 — economy reopens",
        {"pandemic_severity": -0.20, "welfare_index": +0.10, "city_budget": +200_000}),
    NationalEvent(2023, 1, "Recovery_Begins",
        "Post-pandemic recovery — OFW remittances surge",
        {"welfare_index": +0.06, "ofw_remittance": +0.05, "unrest_level": -0.05}),
    NationalEvent(2024, 150, "BBM_Infrastructure",
        "Build Better More reaches province — new road contracts awarded",
        {"infrastructure_quality": +0.08, "city_budget": +500_000,
         "corruption_index": +0.04}),
    NationalEvent(2025, 100, "Pre_Midterm_Spending",
        "Midterm vote-buying intensifies",
        {"corruption_index": +0.04, "dynasty_score": +0.03}),
    NationalEvent(2025, 135, "Midterm_Elections",
        "2025 midterm elections — political realignment",
        {"citizen_trust": -0.04, "unrest_level": +0.05}),
    NationalEvent(2026, 1, "Post_Midterm",
        "New officials take office, fresh promises made",
        {"citizen_trust": +0.03, "unrest_level": -0.04}),
]

# Philippine local election years covered by simulation
ELECTION_CALENDAR = {2022, 2025}
ELECTION_DAY = 135   # approximately May 13-15


@dataclass
class GlobalFactors:
    # Core governance
    institution_strength:     float = 0.50
    corruption_index:         float = 0.25
    welfare_index:            float = 0.55
    audit_strength:           float = 0.40
    media_presence:           float = 0.35
    city_budget:              float = 5_000_000.0
    citizen_trust:            float = 0.50
    unrest_level:             float = 0.15
    dynasty_score:            float = 0.00

    # Province-specific (2020-2026)
    pandemic_severity:        float = 0.00
    ofw_remittance:           float = 0.30
    land_conversion_pressure: float = 0.25
    infrastructure_quality:   float = 0.45
    national_trust:           float = 0.50

    def update_dynasty_score(self, office_holders: list):
        if not office_holders:
            return
        from collections import Counter
        fam_counts = Counter(a.family_id for a in office_holders if a.family_id)
        if not fam_counts:
            self.dynasty_score = 0.0
            return
        top = fam_counts.most_common(1)[0][1]
        self.dynasty_score = top / len(office_holders)

    def apply_corruption_effects(self, delta: float):
        self.corruption_index     = clamp(self.corruption_index     + delta)
        self.citizen_trust        = clamp(self.citizen_trust        - delta * 0.4)
        self.welfare_index        = clamp(self.welfare_index        - delta * 0.2)
        self.unrest_level         = clamp(self.unrest_level         + delta * 0.3)
        self.institution_strength = clamp(self.institution_strength - delta * 0.1)

    def apply_honest_service(self, delta: float):
        self.welfare_index          = clamp(self.welfare_index          + delta * 0.5)
        self.citizen_trust          = clamp(self.citizen_trust          + delta * 0.3)
        self.unrest_level           = clamp(self.unrest_level           - delta * 0.2)
        self.infrastructure_quality = clamp(self.infrastructure_quality + delta * 0.1)

    def natural_decay(self):
        decay = 0.0005 * (1 - self.institution_strength)
        self.welfare_index          = clamp(self.welfare_index          - decay)
        self.infrastructure_quality = clamp(self.infrastructure_quality - decay * 0.5)

    def audit_suppression_from_dynasty(self):
        self.audit_strength = clamp(self.audit_strength - self.dynasty_score * 0.003)

    def apply_national_event(self, event: NationalEvent):
        for fname, delta in event.effects.items():
            if fname == "city_budget":
                self.city_budget = max(0.0, self.city_budget + delta)
            elif fname == "pandemic_severity":
                self.pandemic_severity = clamp(max(0.0, self.pandemic_severity + delta))
            elif hasattr(self, fname):
                setattr(self, fname, clamp(getattr(self, fname) + delta))

    def pandemic_effects(self):
        if self.pandemic_severity > 0.05:
            self.welfare_index = clamp(self.welfare_index - self.pandemic_severity * 0.0002)
            self.city_budget   = max(0.0, self.city_budget - self.pandemic_severity * 100)

    def ofw_welfare_floor(self):
        floor = self.ofw_remittance * 0.25
        if self.welfare_index < floor:
            self.welfare_index = floor

    def to_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in self.__dict__.items()}


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass
class SimClock:
    """
    1 tick = 1 in-game hour.
    Simulation spans 2020-2026 = 7 sim years.
    """
    tick:  int = 0
    hour:  int = 6
    day:   int = 1
    year:  int = 1   # year 1 = 2020, year 7 = 2026

    START_YEAR: int = 2020
    MAX_YEARS:  int = 7

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
    def calendar_year(self) -> int:
        return self.START_YEAR + (self.year - 1)

    @property
    def is_election_day(self) -> bool:
        return (self.calendar_year in ELECTION_CALENDAR and
                self.day == ELECTION_DAY and
                self.hour == 8)

    @property
    def is_done(self) -> bool:
        return self.year > self.MAX_YEARS

    @property
    def label(self) -> str:
        return f"{self.calendar_year} D{self.day} {self.hour:02d}:00"

    def pending_national_events(self) -> List[NationalEvent]:
        """National events that fire at 06:00 on their scheduled day."""
        if self.hour != 6:
            return []
        return [e for e in NATIONAL_EVENTS
                if e.calendar_year == self.calendar_year and e.day == self.day]

    def to_dict(self) -> dict:
        return {
            "tick":          self.tick,
            "hour":          self.hour,
            "day":           self.day,
            "year":          self.year,
            "calendar_year": self.calendar_year,
        }

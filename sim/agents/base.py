"""
agents/base.py
Base Agent class — every person in Barangay Mabuhay inherits from this.
Mesa's Agent gives us the scheduler + model reference for free.
"""

import random
from dataclasses import dataclass, field
from typing import Optional, List
from mesa import Agent


# ── Trait ranges (all [0,1]) ───────────────────────────────────────────────
@dataclass
class Traits:
    integrity:      float = 0.5   # resistance to corrupt choices
    greed:          float = 0.5   # weight on personal wealth gain
    ambition:       float = 0.5   # drives risk-taking, political moves
    family_loyalty: float = 0.5   # weight given to family outcomes
    competence:     float = 0.5   # multiplier on work output
    empathy:        float = 0.5   # affects how much citizen welfare matters

    @classmethod
    def random(cls, bias: dict = None) -> "Traits":
        """
        bias = {'integrity': 0.7} nudges that trait up.
        Everything else randomized with some noise.
        """
        bias = bias or {}
        def val(k):
            base = bias.get(k, 0.5)
            return max(0.0, min(1.0, random.gauss(base, 0.15)))
        return cls(
            integrity      = val("integrity"),
            greed          = val("greed"),
            ambition       = val("ambition"),
            family_loyalty = val("family_loyalty"),
            competence     = val("competence"),
            empathy        = val("empathy"),
        )

    def to_dict(self) -> dict:
        return {k: round(v, 3) for k, v in self.__dict__.items()}


# ── Goal ──────────────────────────────────────────────────────────────────
@dataclass
class Goal:
    key: str
    label: str
    progress: float = 0.0      # 0 to 1
    public: bool = True        # False = hidden / corrupt goal
    priority: float = 1.0

    def advance(self, amount: float):
        self.progress = min(1.0, self.progress + amount)

    def is_complete(self) -> bool:
        return self.progress >= 1.0

    def to_dict(self) -> dict:
        return {"key": self.key, "label": self.label,
                "progress": round(self.progress, 3), "public": self.public}


# ── Memory entry ──────────────────────────────────────────────────────────
@dataclass
class MemoryEntry:
    tick: int
    event: str
    emotional_tag: str = "neutral"   # satisfied | frustrated | fearful | angry


# ── Base Agent ────────────────────────────────────────────────────────────
class BarangayAgent(Agent):
    """
    Every resident of Barangay Mabuhay.
    Subclasses override step() and define their goal pool + schedules.
    """

    # Override in subclasses
    ROLE: str = "citizen"
    HOME_ZONE: str = "resC"
    WORK_ZONE: str = "park"
    TRAIT_BIAS: dict = {}

    def __init__(self, unique_id: int, model, name: str,
                 family_id: Optional[str] = None,
                 dynasty_enabled: bool = True):
        super().__init__(model)

        self._manual_id = unique_id   # store for compatibility
        self.name = name
        self.family_id: Optional[str] = family_id
        self.dynasty_enabled = dynasty_enabled

        # ── Demographics (overridden from CSV when loaded) ─────────────
        self.sex:            str            = "M"
        self.age:            Optional[int]  = None
        self.education_level: Optional[int] = None
        self.social_class:   str            = ""
        self.is_alive:       bool           = True
        self.civil_degree:   Optional[int]  = None
        self.relation_type:  str            = ""
        self.relation_label: str            = ""

        # ── Economic state ─────────────────────────────────────────────
        self.personal_wealth: float = self._starting_wealth()
        self.income_per_day: float  = self._base_income()

        # ── Location ───────────────────────────────────────────────────
        self.current_location: str = self.HOME_ZONE
        self.target_location:  str = self.HOME_ZONE
        self.task_ticks_remaining: int = 0   # how many ticks left on current task
        self.current_task: str = "resting"

        # ── Traits ─────────────────────────────────────────────────────
        self.traits: Traits = Traits.random(self.TRAIT_BIAS)

        # ── Goals (populated by subclass) ──────────────────────────────
        self.goals: List[Goal] = []
        self._init_goals()

        # ── Relationships (agent_id → trust score [-1, 1]) ─────────────
        # Populated by RelationshipGraph, mirrored here for convenience
        self.relationships: dict[int, float] = {}

        # ── Memory (rolling last 20 significant events) ─────────────────
        self.memory: List[MemoryEntry] = []

        # ── Satisfaction ───────────────────────────────────────────────
        self.satisfaction: float = random.uniform(40, 75)   # 0–100

        # ── Pending Qwen decision ──────────────────────────────────────
        self.needs_inference: bool = False
        self.pending_action: Optional[dict] = None  # filled by QwenClient

        # ── Stats tracking ─────────────────────────────────────────────
        self.corrupt_acts: int = 0
        self.honest_acts:  int = 0

    # ── Subclass hooks ────────────────────────────────────────────────────

    def _starting_wealth(self) -> float:
        return random.gauss(15_000, 3_000)   # override in subclasses

    def _base_income(self) -> float:
        return random.gauss(400, 80)          # pesos/day

    def _init_goals(self):
        """Subclasses populate self.goals from their role-specific pool."""
        pass

    # ── Schedule helpers ──────────────────────────────────────────────────

    def get_scheduled_location(self) -> str:
        """
        Returns where this agent should be at the current sim hour.
        Subclasses override with role-specific schedules.
        """
        hour = self.model.clock.hour
        if 22 <= hour or hour < 5:
            return self.HOME_ZONE
        if 8 <= hour < 17:
            return self.WORK_ZONE
        return self.HOME_ZONE

    def start_task(self, location: str, task_label: str, duration_ticks: int):
        self.target_location   = location
        self.current_task      = task_label
        self.task_ticks_remaining = duration_ticks

    # ── Core step ─────────────────────────────────────────────────────────

    def step(self):
        """
        Called every tick by the Mesa scheduler.
        1. Tick down current task.
        2. If task done → decide next action (flag for inference or use schedule).
        3. Update satisfaction from world state.
        """
        # Arrive at target location
        if self.current_location != self.target_location:
            self.current_location = self.target_location
            loc = self.model.locations.get(self.current_location)
            if loc:
                loc.remove_agent(self.unique_id)
            new_loc = self.model.locations.get(self.target_location)
            if new_loc:
                new_loc.add_agent(self.unique_id)

        # Tick down task
        if self.task_ticks_remaining > 0:
            self.task_ticks_remaining -= 1
            self._during_task()
            return

        # Task finished — decide next
        self._on_task_complete()
        self._decide_next()

        # Update satisfaction daily
        if self.model.clock.hour == 22:
            self._update_satisfaction()

    def _during_task(self):
        """Called every tick while executing a task. Override for effects."""
        pass

    def _on_task_complete(self):
        """Called when task_ticks_remaining hits 0."""
        pass

    def _decide_next(self):
        """
        Default: follow schedule.
        Subclasses or QwenClient can override pending_action.
        """
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return

        loc = self.get_scheduled_location()
        self.start_task(loc, "routine", duration_ticks=random.randint(2, 4))

    def _execute_action(self, action: dict):
        """
        Execute a resolved action dict from Qwen or rule-based logic.
        action = {
            "action_id": str,
            "location": str,
            "duration_hours": int,
            "reasoning": str,
            "corruption": bool,   # optional
        }
        """
        loc      = action.get("location", self.HOME_ZONE)
        duration = action.get("duration_hours", 2)
        label    = action.get("action_id", "task")
        is_corrupt = action.get("corruption", False)

        self.start_task(loc, label, duration_ticks=duration)
        self._log_memory(label, emotional_tag="neutral")

        if is_corrupt:
            self.corrupt_acts += 1
            self.model.global_factors.apply_corruption_effects(0.001)
            self.model.log_event(self, "corruption", f"{self.name} engaged in corrupt act: {label}")
        else:
            self.honest_acts += 1

    def _update_satisfaction(self):
        gf = self.model.global_factors
        self.satisfaction += (gf.welfare_index - 0.5) * 5
        self.satisfaction -= gf.corruption_index * 3
        self.satisfaction += (gf.citizen_trust - 0.5) * 2
        self.satisfaction  = max(0, min(100, self.satisfaction))

        if self.satisfaction < 25:
            self.model.global_factors.unrest_level = min(
                1.0, self.model.global_factors.unrest_level + 0.001
            )
            self.model.log_event(self, "civic", f"{self.name} is deeply dissatisfied")

    # ── Memory ────────────────────────────────────────────────────────────

    def _log_memory(self, event: str, emotional_tag: str = "neutral"):
        self.memory.append(
            MemoryEntry(tick=self.model.clock.tick,
                        event=event, emotional_tag=emotional_tag)
        )
        if len(self.memory) > 20:
            self.memory.pop(0)

    def recent_memory_str(self) -> str:
        """Format last 5 memories as a string for Qwen prompt."""
        recent = self.memory[-5:]
        return "; ".join(f"[{m.event}]" for m in recent) or "no notable events"

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "id":               self.unique_id,
            "name":             self.name,
            "role":             self.ROLE,
            "family_id":        self.family_id,
            "sex":              self.sex,
            "age":              self.age,
            "education_level":  self.education_level,
            "social_class":     self.social_class,
            "is_alive":         self.is_alive,
            "civil_degree":     self.civil_degree,
            "relation_type":    self.relation_type,
            "relation_label":   self.relation_label,
            "location":         self.current_location,
            "task":             self.current_task,
            "satisfaction":     round(self.satisfaction, 1),
            "wealth":           round(self.personal_wealth, 2),
            "traits":           self.traits.to_dict(),
            "goals":            [g.to_dict() for g in self.goals],
            "corrupt_acts":     self.corrupt_acts,
            "honest_acts":      self.honest_acts,
        }

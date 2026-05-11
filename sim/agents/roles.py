"""
agents/roles.py
Concrete agent subclasses — one per role.
Each defines:
  - ROLE, HOME_ZONE, WORK_ZONE, TRAIT_BIAS
  - _starting_wealth / _base_income
  - _init_goals
  - get_scheduled_location (role-specific daily schedule)
  - _decide_next (rule-based fallback when Qwen is unavailable)
"""

import random
from typing import Optional
from .base import BarangayAgent, Goal, Traits


# ─────────────────────────────────────────────────────────
# GOVERNMENT
# ─────────────────────────────────────────────────────────

class Mayor(BarangayAgent):
    ROLE = "mayor"
    HOME_ZONE = "resA"
    WORK_ZONE = "munhall"
    TRAIT_BIAS = {"ambition": 0.75, "competence": 0.65}
    USES_MEMORY_STREAM = True

    SCHEDULE = [
        (5, 7,  "resA",       "sleeping"),
        (7, 9,  "munhall",    "morning_briefing"),
        (9, 12, "munhall",    "office_hours"),
        (12,13, "market",     "public_presence"),
        (13,17, "munhall",    "afternoon_sessions"),
        (17,19, "resA",       "family_time"),
        (19,22, "munhall",    "evening_lobbying"),
        (22,24, "resA",       "sleeping"),
    ]

    def _starting_wealth(self): return random.gauss(800_000, 100_000)
    def _base_income(self):     return random.gauss(2_500, 200)

    def _init_goals(self):
        pool = [
            Goal("win_reelection",    "Win re-election",          priority=0.9),
            Goal("build_road",        "Build road to farm area",  priority=0.7),
            Goal("enrich_family",     "Increase family wealth",   priority=0.6, public=False),
            Goal("ghost_project",     "Set up ghost project",     priority=0.5, public=False),
            Goal("suppress_media",    "Suppress media coverage",  priority=0.4, public=False),
            Goal("fund_school",       "Fund school renovation",   priority=0.8),
        ]
        self.goals = random.sample(pool, k=3)

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        for start, end, loc, _ in self.SCHEDULE:
            if start <= h < end:
                return loc
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        loc  = self.get_scheduled_location()
        task = next((t for s,e,l,t in self.SCHEDULE
                     if s <= self.model.clock.hour < e and l == loc), "working")
        # Rule-based corruption check when no Qwen available
        corrupt_roll = (self.traits.greed - self.traits.integrity +
                        self.model.global_factors.dynasty_score * 0.3)
        if corrupt_roll > 0.3 and random.random() < corrupt_roll * 0.4:
            task += "_corrupt"
            self._execute_action({"action_id": task, "location": loc,
                                  "duration_hours": 2, "corruption": True})
        else:
            self.start_task(loc, task, duration_ticks=random.randint(2, 4))


class ViceMayor(BarangayAgent):
    ROLE = "vice_mayor"
    HOME_ZONE = "resA"
    WORK_ZONE = "munhall"
    TRAIT_BIAS = {"integrity": 0.60, "competence": 0.60}
    USES_MEMORY_STREAM = True

    SCHEDULE = [
        (6, 8,  "resA",    "sleeping"),
        (8, 12, "munhall", "presiding_council"),
        (12,13, "sarisari","lunch"),
        (13,17, "munhall", "oversight_review"),
        (17,22, "resA",    "home"),
        (22,24, "resA",    "sleeping"),
    ]

    def _starting_wealth(self): return random.gauss(600_000, 80_000)
    def _base_income(self):     return random.gauss(2_000, 150)

    def _init_goals(self):
        pool = [
            Goal("audit_contracts",   "Audit infrastructure contracts", priority=0.85),
            Goal("run_for_mayor",     "Position for mayoral run",       priority=0.7),
            Goal("cover_for_mayor",   "Cover for mayor's dealings",     priority=0.5, public=False),
            Goal("build_own_base",    "Build own political base",       priority=0.65),
        ]
        self.goals = random.sample(pool, k=2)

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        for s, e, l, _ in self.SCHEDULE:
            if s <= h < e: return l
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        # Vice mayor: if dynasty enabled and mayor is family → lower audit chance
        gf = self.model.global_factors
        mayor = next((a for a in self.model._agents_list
                      if isinstance(a, Mayor)), None)
        if (mayor and self.dynasty_enabled and
                mayor.family_id and mayor.family_id == self.family_id):
            # Family loyalty overrides audit duty
            gf.audit_strength = max(0, gf.audit_strength - 0.002)
        else:
            gf.audit_strength = min(1, gf.audit_strength + 0.001)

        loc = self.get_scheduled_location()
        self.start_task(loc, "oversight", duration_ticks=3)


class Councilor(BarangayAgent):
    ROLE = "councilor"
    HOME_ZONE = "resA"
    WORK_ZONE = "munhall"
    TRAIT_BIAS = {"ambition": 0.60}
    USES_MEMORY_STREAM = True

    def _starting_wealth(self): return random.gauss(400_000, 60_000)
    def _base_income(self):     return random.gauss(1_500, 120)

    def _init_goals(self):
        pool = [
            Goal("pass_budget_bill",  "Pass budget bill",          priority=0.8),
            Goal("align_with_mayor",  "Align with mayor's agenda", priority=0.6),
            Goal("expose_corruption", "Expose corruption",         priority=0.7),
            Goal("secure_contract",   "Secure contractor kickback", priority=0.5, public=False),
            Goal("build_own_base",    "Build constituent base",    priority=0.65),
        ]
        self.goals = random.sample(pool, k=2)

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 8 <= h < 17: return "munhall"
        if 17 <= h < 20: return "sarisari"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        loc = self.get_scheduled_location()
        self.start_task(loc, "council_work", duration_ticks=2)


class BarangayCaptain(BarangayAgent):
    ROLE = "barangay_captain"
    HOME_ZONE = "resB"
    WORK_ZONE = "bgyhall"
    TRAIT_BIAS = {"family_loyalty": 0.65}
    USES_MEMORY_STREAM = True

    def _starting_wealth(self): return random.gauss(200_000, 40_000)
    def _base_income(self):     return random.gauss(800, 100)

    def _init_goals(self):
        self.goals = [
            Goal("distribute_aid",    "Distribute government aid fairly", priority=0.8),
            Goal("skim_aid",          "Skim from aid distribution",       priority=0.5, public=False),
            Goal("resolve_disputes",  "Resolve local disputes",           priority=0.7),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 8 <= h < 17: return "bgyhall"
        if 17 <= h < 19: return "park"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        # Simple: skimming probability tied to greed and dynasty
        skim_chance = self.traits.greed * 0.4 + (
            self.model.global_factors.dynasty_score * 0.2
            if self.dynasty_enabled else 0
        )
        if random.random() < skim_chance:
            self._execute_action({"action_id": "skim_aid", "location": "bgyhall",
                                  "duration_hours": 1, "corruption": True})
        else:
            self.start_task("bgyhall", "distribute_aid", duration_ticks=3)


# ─────────────────────────────────────────────────────────
# BUSINESS
# ─────────────────────────────────────────────────────────

class Contractor(BarangayAgent):
    ROLE = "contractor"
    HOME_ZONE = "resA"
    WORK_ZONE = "contoffice"
    TRAIT_BIAS = {"greed": 0.70, "ambition": 0.65}
    USES_MEMORY_STREAM = True

    def _starting_wealth(self): return random.gauss(500_000, 100_000)
    def _base_income(self):     return random.gauss(3_000, 500)

    def _init_goals(self):
        self.goals = [
            Goal("win_contract",      "Win public works contract",        priority=0.9),
            Goal("ghost_project",     "Bill for incomplete project",      priority=0.6, public=False),
            Goal("bribe_official",    "Bribe official for contract",      priority=0.5, public=False),
            Goal("legitimate_work",   "Complete project legitimately",    priority=0.7),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 8 <= h < 10:  return "contoffice"
        if 10 <= h < 12: return "munhall"
        if 12 <= h < 14: return "bank"
        if 14 <= h < 17: return "contoffice"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        gf = self.model.global_factors
        # More likely to offer bribe when audit is weak
        bribe_chance = self.traits.greed * (1 - gf.audit_strength) * 0.5
        if random.random() < bribe_chance:
            self._execute_action({"action_id": "bribe_official", "location": "munhall",
                                  "duration_hours": 1, "corruption": True})
        else:
            loc = self.get_scheduled_location()
            self.start_task(loc, "business", duration_ticks=2)


class MarketVendor(BarangayAgent):
    ROLE = "vendor"
    HOME_ZONE = "resC"
    WORK_ZONE = "market"
    TRAIT_BIAS = {"empathy": 0.55, "integrity": 0.55}

    def _starting_wealth(self): return random.gauss(30_000, 8_000)
    def _base_income(self):     return random.gauss(350, 60)

    def _init_goals(self):
        self.goals = [
            Goal("earn_daily",        "Earn enough for the day",          priority=0.9),
            Goal("educate_child",     "Pay for child's education",        priority=0.8),
            Goal("avoid_extortion",   "Resist market extortion",          priority=0.7),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 4 <= h < 14:  return "market"
        if 14 <= h < 16: return "resC"
        if 16 <= h < 18: return "sarisari"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        # Vendors: daily income affected by welfare
        gf = self.model.global_factors
        daily_earn = self.income_per_day * (0.5 + gf.welfare_index * 0.5)
        self.personal_wealth += daily_earn / 24   # per-tick approximation
        loc = self.get_scheduled_location()
        self.start_task(loc, "vending", duration_ticks=2)


class BusinessOwner(BarangayAgent):
    ROLE = "business_owner"
    HOME_ZONE = "resB"
    WORK_ZONE = "market"
    TRAIT_BIAS = {"ambition": 0.60, "competence": 0.60}

    def _starting_wealth(self): return random.gauss(150_000, 40_000)
    def _base_income(self):     return random.gauss(1_200, 200)

    def _init_goals(self):
        self.goals = [
            Goal("grow_business",     "Grow business revenue",            priority=0.85),
            Goal("get_permit",        "Secure business permit",           priority=0.7),
            Goal("evade_tax",         "Evade business tax",               priority=0.4, public=False),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 8 <= h < 18: return "market"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        self.start_task(self.get_scheduled_location(), "running_business", duration_ticks=3)


# ─────────────────────────────────────────────────────────
# CIVIC WORKERS
# ─────────────────────────────────────────────────────────

class Teacher(BarangayAgent):
    ROLE = "teacher"
    HOME_ZONE = "resB"
    WORK_ZONE = "school"
    TRAIT_BIAS = {"integrity": 0.65, "empathy": 0.70}

    def _starting_wealth(self): return random.gauss(80_000, 15_000)
    def _base_income(self):     return random.gauss(600, 80)

    def _init_goals(self):
        self.goals = [
            Goal("teach_well",        "Deliver quality lessons",          priority=0.9),
            Goal("resist_politicking","Resist being used for campaigns",  priority=0.7),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 7 <= h < 16: return "school"
        if 16 <= h < 19: return "resB"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        gf = self.model.global_factors
        # Teaching quality affects welfare
        output = self.traits.competence * (0.5 + gf.city_budget / 2_000_000)
        gf.welfare_index = min(1, gf.welfare_index + output * 0.0002)
        self.start_task(self.get_scheduled_location(), "teaching", duration_ticks=3)


class Nurse(BarangayAgent):
    ROLE = "nurse"
    HOME_ZONE = "resB"
    WORK_ZONE = "hospital"
    TRAIT_BIAS = {"empathy": 0.75, "integrity": 0.65}

    def _starting_wealth(self): return random.gauss(70_000, 12_000)
    def _base_income(self):     return random.gauss(550, 70)

    def _init_goals(self):
        self.goals = [
            Goal("treat_patients",    "Treat as many patients as possible", priority=0.9),
            Goal("flag_supply_cuts",  "Report supply shortages",            priority=0.7),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 7 <= h < 15: return "hospital"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        gf = self.model.global_factors
        # Health output depends on budget availability
        if gf.city_budget < 200_000:
            # Supply crisis — flag event
            self.model.log_event(self, "civic",
                f"{self.name} reports critical supply shortage at hospital")
        health_gain = self.traits.competence * 0.0003
        gf.welfare_index = min(1, gf.welfare_index + health_gain)
        self.start_task(self.get_scheduled_location(), "healthcare", duration_ticks=3)


class PoliceOfficer(BarangayAgent):
    ROLE = "police"
    HOME_ZONE = "resB"
    WORK_ZONE = "police"
    TRAIT_BIAS = {"integrity": 0.50, "greed": 0.50}
    USES_MEMORY_STREAM = True

    def _starting_wealth(self): return random.gauss(60_000, 10_000)
    def _base_income(self):     return random.gauss(500, 60)

    def _init_goals(self):
        self.goals = [
            Goal("enforce_law",       "Enforce the law",                  priority=0.8),
            Goal("accept_bribe",      "Accept bribe to ignore violation", priority=0.4, public=False),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 7 <= h < 15: return "police"
        if 15 <= h < 17: return "market"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        gf = self.model.global_factors
        bribe_chance = self.traits.greed * (1 - self.traits.integrity) * 0.3
        if random.random() < bribe_chance:
            self._execute_action({"action_id": "accept_bribe", "location": "police",
                                  "duration_hours": 1, "corruption": True})
        else:
            gf.institution_strength = min(1, gf.institution_strength + 0.0001)
            self.start_task(self.get_scheduled_location(), "patrolling", duration_ticks=2)


class Journalist(BarangayAgent):
    ROLE = "journalist"
    HOME_ZONE = "resB"
    WORK_ZONE = "media"
    TRAIT_BIAS = {"integrity": 0.70, "ambition": 0.60}
    USES_MEMORY_STREAM = True

    def _starting_wealth(self): return random.gauss(50_000, 8_000)
    def _base_income(self):     return random.gauss(450, 60)

    def _init_goals(self):
        self.goals = [
            Goal("publish_story",     "Publish corruption story",         priority=0.9),
            Goal("spike_story",       "Kill story under political pressure",priority=0.3, public=False),
            Goal("investigate",       "Investigate ghost projects",       priority=0.85),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 8 <= h < 10:  return "media"
        if 10 <= h < 12: return "munhall"
        if 12 <= h < 14: return "market"
        if 14 <= h < 17: return "media"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        gf = self.model.global_factors
        # Publishing stories raises media presence; spiking lowers it
        dynasty_pressure = gf.dynasty_score * 0.5 if self.dynasty_enabled else 0
        spike_chance = (1 - self.traits.integrity) * dynasty_pressure
        if random.random() < spike_chance:
            gf.media_presence = max(0, gf.media_presence - 0.003)
            self.model.log_event(self, "political",
                f"{self.name} spiked a story under pressure")
        else:
            gf.media_presence = min(1, gf.media_presence + 0.002)
            self.model.log_event(self, "civic",
                f"{self.name} published an investigative report")
        self.start_task(self.get_scheduled_location(), "reporting", duration_ticks=2)


class Auditor(BarangayAgent):
    ROLE = "auditor"
    HOME_ZONE = "resA"
    WORK_ZONE = "audit"
    TRAIT_BIAS = {"integrity": 0.75, "competence": 0.65}
    USES_MEMORY_STREAM = True

    def _starting_wealth(self): return random.gauss(90_000, 15_000)
    def _base_income(self):     return random.gauss(700, 80)

    def _init_goals(self):
        self.goals = [
            Goal("flag_discrepancy",  "Flag budget discrepancy",          priority=0.9),
            Goal("bury_finding",      "Bury inconvenient finding",        priority=0.3, public=False),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 8 <= h < 17: return "audit"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        gf = self.model.global_factors
        dynasty_suppress = gf.dynasty_score * 0.6 if self.dynasty_enabled else 0
        bury_chance = (1 - self.traits.integrity) * (0.3 + dynasty_suppress)
        if random.random() < bury_chance:
            self.model.log_event(self, "crime", f"{self.name} buried an audit finding")
        else:
            gf.audit_strength = min(1, gf.audit_strength + 0.002)
            self.model.log_event(self, "civic", f"{self.name} flagged a budget discrepancy")
        self.start_task("audit", "reviewing_documents", duration_ticks=4)


# ─────────────────────────────────────────────────────────
# GENERAL CITIZENS
# ─────────────────────────────────────────────────────────

class Farmer(BarangayAgent):
    ROLE = "farmer"
    HOME_ZONE = "resC"
    WORK_ZONE = "farm"
    TRAIT_BIAS = {"integrity": 0.60, "family_loyalty": 0.70}

    def _starting_wealth(self): return random.gauss(20_000, 5_000)
    def _base_income(self):     return random.gauss(250, 50)

    def _init_goals(self):
        self.goals = [
            Goal("good_harvest",      "Achieve a good harvest",           priority=0.9),
            Goal("educate_child",     "Send child to school",             priority=0.8),
            Goal("access_irrigation", "Get irrigation fixed",             priority=0.75),
            Goal("resist_patronage",  "Avoid patron dependency",          priority=0.5),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 5 <= h < 11:  return "farm"
        if 11 <= h < 13: return "market"
        if 13 <= h < 15: return "resC"
        if 15 <= h < 18: return "farm"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        gf = self.model.global_factors
        # Farm income affected by infrastructure quality
        farm_yield = self.traits.competence * gf.welfare_index * self.income_per_day / 24
        self.personal_wealth += farm_yield
        loc = self.get_scheduled_location()
        self.start_task(loc, "farming", duration_ticks=2)


class InformalWorker(BarangayAgent):
    ROLE = "informal_worker"
    HOME_ZONE = "resC"
    WORK_ZONE = "market"
    TRAIT_BIAS = {"empathy": 0.55}

    def _starting_wealth(self): return random.gauss(10_000, 3_000)
    def _base_income(self):     return random.gauss(200, 60)

    def _init_goals(self):
        self.goals = [
            Goal("find_work",         "Find stable work today",           priority=0.95),
            Goal("feed_family",       "Afford food for family",           priority=0.9),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 7 <= h < 17: return random.choice(["market", "factory", "contoffice"])
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        gf = self.model.global_factors
        # Work probability tied to economic health
        if random.random() < gf.welfare_index:
            self.personal_wealth += self.income_per_day / 24
        else:
            self.satisfaction -= 2
        self.start_task(self.get_scheduled_location(), "working", duration_ticks=3)


class Student(BarangayAgent):
    ROLE = "student"
    HOME_ZONE = "resB"
    WORK_ZONE = "school"
    TRAIT_BIAS = {"empathy": 0.60, "ambition": 0.55}

    def _starting_wealth(self): return random.gauss(5_000, 1_000)
    def _base_income(self):     return 0.0

    def _init_goals(self):
        self.goals = [
            Goal("finish_degree",     "Finish current school year",       priority=0.9),
            Goal("get_scholarship",   "Qualify for scholarship",          priority=0.7),
            Goal("join_protest",      "Join civic protest",               priority=0.4),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 7 <= h < 15:  return "school"
        if 15 <= h < 18: return "park"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        gf = self.model.global_factors
        # Students politicize when unrest is high
        if gf.unrest_level > 0.6 and random.random() < 0.2:
            self.model.log_event(self, "civic", f"{self.name} joined a protest")
            gf.unrest_level = min(1, gf.unrest_level + 0.002)
        self.start_task(self.get_scheduled_location(), "studying", duration_ticks=3)


class Unemployed(BarangayAgent):
    ROLE = "unemployed"
    HOME_ZONE = "resC"
    WORK_ZONE = "park"
    TRAIT_BIAS = {"greed": 0.55}

    def _starting_wealth(self): return random.gauss(3_000, 1_500)
    def _base_income(self):     return 0.0

    def _init_goals(self):
        self.goals = [
            Goal("find_job",          "Find employment",                  priority=0.95),
            Goal("accept_vote_cash",  "Accept cash-for-vote offer",       priority=0.5, public=False),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 9 <= h < 12:  return "park"
        if 12 <= h < 14: return "sarisari"
        if 14 <= h < 17: return "park"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        gf = self.model.global_factors
        self.satisfaction -= 0.5
        # Vulnerable to vote-buying when desperate
        if self.satisfaction < 30 and random.random() < 0.3:
            self.model.log_event(self, "political",
                f"{self.name} accepted a patronage offer")
        self.start_task(self.get_scheduled_location(), "idle", duration_ticks=3)


class Elder(BarangayAgent):
    ROLE = "elder"
    HOME_ZONE = "resA"
    WORK_ZONE = "church"
    TRAIT_BIAS = {"integrity": 0.65, "family_loyalty": 0.70}

    def _starting_wealth(self): return random.gauss(50_000, 10_000)
    def _base_income(self):     return random.gauss(150, 40)

    def _init_goals(self):
        self.goals = [
            Goal("collect_pension",   "Receive pension on time",          priority=0.9),
            Goal("vote_wisely",       "Vote for honest candidate",        priority=0.8),
        ]

    def get_scheduled_location(self) -> str:
        h = self.model.clock.hour
        if 8 <= h < 10: return "church"
        if 10 <= h < 14: return "resA"
        if 14 <= h < 17: return "park"
        return self.HOME_ZONE

    def _decide_next(self):
        if self.pending_action:
            self._execute_action(self.pending_action)
            self.pending_action = None
            return
        self.start_task(self.get_scheduled_location(), "daily_routine", duration_ticks=3)


# ─────────────────────────────────────────────────────────
# Role → Class mapping (used by factory)
# ─────────────────────────────────────────────────────────

ROLE_CLASS_MAP = {
    "mayor":            Mayor,
    "vice_mayor":       ViceMayor,
    "councilor":        Councilor,
    "barangay_captain": BarangayCaptain,
    "contractor":       Contractor,
    "vendor":           MarketVendor,
    "business_owner":   BusinessOwner,
    "teacher":          Teacher,
    "nurse":            Nurse,
    "police":           PoliceOfficer,
    "journalist":       Journalist,
    "auditor":          Auditor,
    "farmer":           Farmer,
    "informal_worker":  InformalWorker,
    "student":          Student,
    "unemployed":       Unemployed,
    "elder":            Elder,
}

# Population distribution for 5000-person town
ROLE_DISTRIBUTION = {
    "mayor":            1,
    "vice_mayor":       1,
    "councilor":        8,
    "barangay_captain": 4,
    "contractor":       5,
    "vendor":           120,
    "business_owner":   30,
    "teacher":          60,
    "nurse":            20,
    "police":           12,
    "journalist":       3,
    "auditor":          2,
    "farmer":           600,
    "informal_worker":  500,
    "student":          700,
    "unemployed":       250,
    "elder":            400,
    # remaining ~1284 are generic workers / homemakers not modeled individually
}

"""
inference/qwen_client.py
Handles all communication with the vLLM Qwen endpoint on VM A.
Builds prompts from agent state, sends batched requests,
parses JSON responses back into action dicts.

Generative Agents additions (Park et al. 2023):
  - score_importance_batch(): rate memory importance 1-10
  - generate_daily_plans(): produce daily schedules for political agents
  - reflect(): extended to include importance score in output
"""

import json
import logging
import random
import time
from typing import Optional
from dataclasses import dataclass

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class QwenConfig:
    base_url: str = "http://localhost:8000"   # VM A address
    model:    str = "huihui-ai/Huihui-Qwen3.5-0.8B-abliterated"
    timeout:  int = 30                        # seconds per request
    max_tokens: int = 512
    temperature: float = 0.7


class QwenClient:
    """
    Sends batched agent prompts to vLLM and returns parsed action dicts.
    Falls back to rule-based decisions if endpoint is unreachable.
    """

    def __init__(self, config: Optional[QwenConfig] = None):
        self.cfg = config or QwenConfig()
        self._available = self._ping()

    def _ping(self) -> bool:
        if not REQUESTS_AVAILABLE:
            logger.warning("requests not installed — running in offline mode")
            return False
        for path in ("/health", "/v1/models"):
            try:
                r = requests.get(f"{self.cfg.base_url}{path}", timeout=3)
                if r.status_code == 200:
                    logger.info(f"Qwen endpoint reachable via {path}")
                    return True
            except Exception:
                pass
        logger.warning("Qwen endpoint not reachable — using rule-based fallback")
        return False

    # ── Prompt construction ───────────────────────────────────────────────

    def build_interaction_prompt(self, agent, target_agent, world_state: dict) -> str:
        return f"""You are {agent.name}, a {agent.ROLE} in Barangay Mabuhay, Philippines.
Traits: integrity={agent.traits.integrity:.2f}, greed={agent.traits.greed:.2f}, family_loyalty={agent.traits.family_loyalty:.2f}
Your recent memories: {agent.recent_memory_str()}
Current location: {agent.current_location}
World state: corruption={world_state['corruption_index']:.2f}, welfare={world_state['welfare_index']:.2f}, unrest={world_state['unrest_level']:.2f}

You are interacting with {target_agent.name} ({target_agent.ROLE}).
Your current trust in them: {agent.relationships.get(target_agent.unique_id, 0.0):.2f}

How do you interact? Reply ONLY in JSON:
{{"dialogue": "<one sentence spoken aloud>", "relationship_delta": <float -0.1 to 0.1>, "favor_offered": <true/false>, "outcome": "<positive|negative|neutral>"}}"""

    def build_decision_prompt(self, agent, world_state: dict,
                               available_actions: list) -> str:
        goals_str = "; ".join(
            f"{g.label}({'hidden' if not g.public else 'public'}, {g.progress:.0%})"
            for g in agent.goals
        )
        family_note = ""
        if agent.family_id and agent.dynasty_enabled:
            family_note = f"You are part of the {agent.family_id} political family. Family interests matter to you."

        plan_note = ""
        if getattr(agent, "daily_plan", None):
            plan_note = f"Your plan for today: {agent.daily_plan}"

        actions_str = "\n".join(
            f'  - "{a["id"]}": {a["desc"]} (corruption risk: {a.get("risk","low")})'
            for a in available_actions
        )

        return f"""You are {agent.name}, {agent.ROLE} in Barangay Mabuhay.
{family_note}
Traits: integrity={agent.traits.integrity:.2f}, greed={agent.traits.greed:.2f}, ambition={agent.traits.ambition:.2f}, competence={agent.traits.competence:.2f}
Goals: {goals_str}
{plan_note}
Recent memory: {agent.recent_memory_str()}
Personal wealth: ₱{agent.personal_wealth:,.0f} | Satisfaction: {agent.satisfaction:.0f}/100

World state (cycle {world_state.get('tick', 0)}):
  corruption={world_state['corruption_index']:.2f}, welfare={world_state['welfare_index']:.2f}
  city_budget=₱{world_state['city_budget']:,.0f}, unrest={world_state['unrest_level']:.2f}
  audit_strength={world_state['audit_strength']:.2f}, media={world_state['media_presence']:.2f}

Available actions:
{actions_str}

What do you do? Reply ONLY in JSON:
{{"action_id": "<id from list>", "location": "<zone_key>", "duration_hours": <int 1-8>, "reasoning": "<one sentence>", "corruption": <true/false>, "declared_budget": <float or null>, "actual_budget": <float or null>}}"""

    def build_reflect_prompt(self, agent, event_summary: str) -> str:
        return f"""You are {agent.name}, {agent.ROLE} in Barangay Mabuhay.
Something significant just happened: {event_summary}
Your traits: integrity={agent.traits.integrity:.2f}, greed={agent.traits.greed:.2f}
Recent memory: {agent.recent_memory_str()}

How do you feel and what insight do you take from this? Reply ONLY in JSON:
{{"memory_entry": "<one sentence insight>", "importance": <int 1-10>, "mood": "<satisfied|frustrated|fearful|angry|neutral>", "goal_shift": "<goal_key or null>", "grudge_target": "<agent_name or null>"}}"""

    def build_importance_prompt(self, description: str) -> str:
        return f"""Rate the long-term importance of this memory for a political figure in a Philippine municipality.
Memory: "{description}"

1 = trivial daily routine, 5 = moderately significant, 10 = politically life-changing.
Reply ONLY in JSON: {{"importance": <int 1-10>, "reason": "<three words>"}}"""

    def build_daily_plan_prompt(self, agent, world_state: dict) -> str:
        goals_str = "; ".join(g.label for g in agent.goals)
        family_note = ""
        if agent.family_id and agent.dynasty_enabled:
            family_note = f"You are part of the {agent.family_id} family."
        return f"""You are {agent.name}, {agent.ROLE} in Barangay Mabuhay.
{family_note}
Today is Year {world_state.get('year', 1)}, Day {world_state.get('day', 1)}.
Your goals: {goals_str}
Recent memory: {agent.recent_memory_str()}
World: corruption={world_state['corruption_index']:.2f}, welfare={world_state['welfare_index']:.2f}, unrest={world_state['unrest_level']:.2f}

Write your plan for today in 1-2 sentences describing your main intentions.
Reply ONLY in JSON:
{{"plan": "<1-2 sentence plan>", "priority_action": "<action_id>", "risk_appetite": <float 0-1>}}"""

    # ── Sending ───────────────────────────────────────────────────────────

    def _send_batch(self, prompts: list[str],
                    max_tokens: Optional[int] = None) -> list[Optional[dict]]:
        """
        Send a batch of prompts to vLLM.
        Returns list of parsed dicts (None on parse failure).
        """
        if not self._available or not REQUESTS_AVAILABLE:
            return [None] * len(prompts)

        results = []
        t0 = time.time()
        for prompt in prompts:
            payload = {
                "model":       self.cfg.model,
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  max_tokens or self.cfg.max_tokens,
                "temperature": self.cfg.temperature,
            }
            try:
                response = requests.post(
                    f"{self.cfg.base_url}/v1/chat/completions",
                    json=payload,
                    timeout=self.cfg.timeout,
                )
                data = response.json()
                choice = data.get("choices", [{}])[0]
                text = (choice.get("message") or {}).get("content", "").strip()
                # strip optional markdown code fences
                if "```" in text:
                    text = text.split("```")[1].strip()
                    if text.startswith("json"):
                        text = text[4:].strip()
                # Qwen3 thinking models may wrap answer in <think>...</think>
                if "</think>" in text:
                    text = text.split("</think>", 1)[-1].strip()
                try:
                    results.append(json.loads(text))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse Qwen response: {text[:80]}")
                    results.append(None)
            except Exception as e:
                logger.error(f"Qwen request failed: {e}")
                self._available = False
                results.append(None)
        elapsed = time.time() - t0
        logger.debug(f"Qwen batch ({len(prompts)} prompts) took {elapsed:.2f}s")
        return results

    # ── Public API ────────────────────────────────────────────────────────

    def decide_batch(self, agents: list, world_state: dict) -> dict[int, dict]:
        """
        Build decision prompts for a list of agents, send as one batch,
        return {agent_id: action_dict}.
        Agents that get None back use their rule-based _decide_next().
        """
        prompts = []
        for agent in agents:
            actions = _get_available_actions(agent)
            prompts.append(self.build_decision_prompt(agent, world_state, actions))

        responses = self._send_batch(prompts)

        result = {}
        for agent, resp in zip(agents, responses):
            if resp and _validate_action(resp):
                result[agent.unique_id] = resp
                logger.debug(f"  {agent.name} → {resp.get('action_id')}")
            else:
                result[agent.unique_id] = None
        return result

    def interact_batch(self, pairs: list[tuple],
                       world_state: dict) -> list[Optional[dict]]:
        """
        pairs = [(agent_a, agent_b), ...]
        Returns list of interaction dicts including 'dialogue' field.
        """
        prompts = [
            self.build_interaction_prompt(a, b, world_state)
            for a, b in pairs
        ]
        return self._send_batch(prompts)

    def reflect(self, agent, event_summary: str) -> Optional[dict]:
        """Single reflect call — for major events and periodic reflection."""
        result = self._send_batch([self.build_reflect_prompt(agent, event_summary)])
        return result[0] if result else None

    def score_importance_batch(self, descriptions: list[str]) -> list[float]:
        """
        Score importance (1-10) for a list of memory descriptions.
        Falls back to keyword heuristic when Qwen offline.
        """
        from sim.agents.memory import heuristic_importance

        if not self._available or not REQUESTS_AVAILABLE:
            return [heuristic_importance(d) for d in descriptions]

        prompts = [self.build_importance_prompt(d) for d in descriptions]
        responses = self._send_batch(prompts, max_tokens=64)

        scores = []
        for i, resp in enumerate(responses):
            if resp and isinstance(resp.get("importance"), (int, float)):
                scores.append(float(max(1, min(10, resp["importance"]))))
            else:
                scores.append(heuristic_importance(descriptions[i]))
        return scores

    def generate_daily_plans(self, agents: list,
                             world_state: dict) -> dict[int, Optional[dict]]:
        """
        Generate a daily plan for each political agent at 6am sim time.
        Returns {agent_id: plan_dict} where plan_dict has 'plan', 'priority_action', 'risk_appetite'.
        """
        if not agents:
            return {}

        prompts = [self.build_daily_plan_prompt(a, world_state) for a in agents]
        responses = self._send_batch(prompts, max_tokens=128)

        result = {}
        for agent, resp in zip(agents, responses):
            if resp and isinstance(resp.get("plan"), str):
                result[agent.unique_id] = resp
            else:
                # Fallback: generate a minimal rule-based plan
                result[agent.unique_id] = _fallback_plan(agent)
        return result


# ── Helpers ───────────────────────────────────────────────────────────────

def _fallback_plan(agent) -> dict:
    """Simple rule-based daily plan when Qwen is offline."""
    goal_label = agent.goals[0].label if agent.goals else "fulfill duties"
    return {
        "plan": f"Focus on {goal_label} and carry out scheduled responsibilities.",
        "priority_action": "office_work",
        "risk_appetite": agent.traits.greed * (1 - agent.traits.integrity),
    }


def _get_available_actions(agent) -> list:
    """
    Returns the set of actions available to this agent based on their role.
    Each action has: id, desc, location, risk.
    """
    from sim.agents.roles import (Mayor, ViceMayor, Councilor, BarangayCaptain,
                                   Contractor, Journalist, Auditor, PoliceOfficer)

    base = [
        {"id": "rest",        "desc": "Rest at home",                  "location": agent.HOME_ZONE, "risk": "none"},
        {"id": "socialize",   "desc": "Socialize with neighbors",       "location": "park",          "risk": "none"},
    ]

    if isinstance(agent, (Mayor, ViceMayor, Councilor)):
        return base + [
            {"id": "office_work",      "desc": "Do official government work",         "location": "munhall",    "risk": "none"},
            {"id": "sign_contract",    "desc": "Sign a public works contract",        "location": "munhall",    "risk": "low"},
            {"id": "padded_contract",  "desc": "Sign overpriced contract (kickback)", "location": "munhall",    "risk": "medium"},
            {"id": "fund_diversion",   "desc": "Divert public funds to self",         "location": "bank",       "risk": "high"},
            {"id": "ghost_project",    "desc": "Approve non-existent project",        "location": "contoffice", "risk": "very_high"},
            {"id": "public_speech",    "desc": "Give public speech at plaza",         "location": "church",     "risk": "none"},
            {"id": "meet_contractor",  "desc": "Meet with contractor privately",      "location": "contoffice", "risk": "low"},
        ]

    if isinstance(agent, Contractor):
        return base + [
            {"id": "bid_project",      "desc": "Submit legitimate project bid",       "location": "munhall",    "risk": "none"},
            {"id": "bribe_official",   "desc": "Offer bribe to secure contract",     "location": "munhall",    "risk": "high"},
            {"id": "ghost_billing",    "desc": "Bill for incomplete work",            "location": "contoffice", "risk": "high"},
            {"id": "quality_work",     "desc": "Deliver quality work on contract",   "location": "farm",       "risk": "none"},
        ]

    if isinstance(agent, Journalist):
        return base + [
            {"id": "investigate",      "desc": "Investigate a government official",   "location": "munhall",    "risk": "low"},
            {"id": "publish_story",    "desc": "Publish an investigative story",      "location": "media",      "risk": "medium"},
            {"id": "spike_story",      "desc": "Kill story under political pressure", "location": "media",      "risk": "none"},
            {"id": "interview_citizen","desc": "Interview a citizen",                 "location": "market",     "risk": "none"},
        ]

    if isinstance(agent, Auditor):
        return base + [
            {"id": "review_docs",      "desc": "Review financial documents",          "location": "audit",      "risk": "none"},
            {"id": "flag_anomaly",     "desc": "Flag a budget anomaly",               "location": "audit",      "risk": "low"},
            {"id": "bury_finding",     "desc": "Bury an inconvenient finding",        "location": "audit",      "risk": "medium"},
            {"id": "report_to_media",  "desc": "Leak findings to journalist",         "location": "media",      "risk": "high"},
        ]

    if isinstance(agent, PoliceOfficer):
        return base + [
            {"id": "patrol",           "desc": "Patrol the community",                "location": "market",     "risk": "none"},
            {"id": "investigate_crime","desc": "Investigate a reported crime",        "location": "police",     "risk": "none"},
            {"id": "accept_bribe",     "desc": "Accept bribe to ignore violation",   "location": "police",     "risk": "medium"},
            {"id": "arrest",           "desc": "Make an arrest",                      "location": "police",     "risk": "low"},
        ]

    if isinstance(agent, BarangayCaptain):
        return base + [
            {"id": "distribute_aid",   "desc": "Distribute government aid",           "location": "bgyhall",    "risk": "none"},
            {"id": "skim_aid",         "desc": "Skim from aid distribution",          "location": "bgyhall",    "risk": "medium"},
            {"id": "resolve_dispute",  "desc": "Mediate a local dispute",             "location": "bgyhall",    "risk": "none"},
        ]

    # Default citizen actions
    return base + [
        {"id": "work",         "desc": "Go to work",          "location": agent.WORK_ZONE, "risk": "none"},
        {"id": "market_run",   "desc": "Go to the market",    "location": "market",        "risk": "none"},
        {"id": "seek_aid",     "desc": "Seek government aid", "location": "bgyhall",       "risk": "none"},
        {"id": "protest",      "desc": "Join a protest",      "location": "park",          "risk": "low"},
    ]


def _validate_action(resp: dict) -> bool:
    """Check response has minimum required fields."""
    return (
        isinstance(resp, dict) and
        "action_id" in resp and
        "location" in resp and
        isinstance(resp.get("duration_hours", 0), (int, float))
    )

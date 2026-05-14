# sim/onit/vllm_client.py
# Async batch inference for tier-2 agents via vLLM's OpenAI-compatible API.

import asyncio, json, re
from openai import AsyncOpenAI
from .constants import MODEL_NAME, VLLM_BASE_URL, TIER2_BATCH_SIZE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .agent_loader import Agent

_client = AsyncOpenAI(base_url=VLLM_BASE_URL, api_key="dummy")

VALID_ACTIONS = {
    "lay_low", "secure_contract", "suppress_rival", "place_ally",
    "vote_ordinance", "bribe_official", "publish_story", "make_plan",
}


def _build_action_prompt(agent: "Agent", world_state: dict,
                          memories: list[dict], plan: str) -> str:
    mem_block = ""
    if memories:
        lines = [f"  [Tick {m['tick']}] {m['event']}  (importance {m['importance']}/10)"
                 for m in memories]
        mem_block = "MEMORIES:\n" + "\n".join(lines) + "\n\n"

    plan_block = f"TODAY'S PLAN: {plan}\n\n" if plan else ""

    return (
        f"You are {agent.name}, {agent.role} in Mabuhay Province.\n"
        f"Goals: {' | '.join(agent.goals)}\n"
        f"Traits: integrity={agent.integrity:.2f} greed={agent.greed:.2f} "
        f"ambition={agent.ambition:.2f}\n\n"
        f"{mem_block}"
        f"{plan_block}"
        f"WORLD STATE (Tick {world_state['tick']}):\n"
        f"  dynasty={world_state['dynasty_score']:.0f}  "
        f"corruption={world_state['corruption']:.0f}  "
        f"scrutiny={world_state['scrutiny']:.0f}  "
        f"trust={world_state['civic_trust']:.0f}  "
        f"election_in={world_state['election_in']}\n"
        f"  events: {world_state.get('recent_events','')[:150]}\n\n"
        f"Choose ONE action. Reply with JSON only:\n"
        f'{{"action":"<name>","params":{{"key":"value"}},"reasoning":"<1 sentence>"}}\n'
        f"Valid actions: lay_low, secure_contract(agency,value), suppress_rival(rival_name),\n"
        f"  place_ally(ally_name,position), vote_ordinance(bill,stance),\n"
        f"  bribe_official(official_name,amount), publish_story(target,allegation)"
    )


def _build_plan_prompt(agent: "Agent", world_state: dict) -> str:
    return (
        f"You are {agent.name}, {agent.role} in Mabuhay Province.\n"
        f"Goals: {' | '.join(agent.goals)}\n\n"
        f"World state: dynasty={world_state['dynasty_score']:.0f}  "
        f"corruption={world_state['corruption']:.0f}  "
        f"scrutiny={world_state['scrutiny']:.0f}  "
        f"election_in={world_state['election_in']}\n\n"
        f"In 2 sentences, state your plan for today as {agent.name}. "
        f"Be specific about what you intend to do and why."
    )


def _parse_action(raw: str) -> dict | None:
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            d = json.loads(m.group())
            if d.get("action") in VALID_ACTIONS:
                return d
    except Exception:
        pass
    return None


async def _single_call(prompt: str, max_tokens: int = 256) -> str:
    resp = await _client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return resp.choices[0].message.content or ""


async def batch_act(
    agents: list["Agent"],
    world_state: dict,
    memories_map: dict[int, list[dict]],
    plans_map:    dict[int, str],
) -> dict[int, dict]:
    """
    Run action inference for a list of tier-2 agents in concurrent batches.
    Returns {agent_id: parsed_action_dict}.
    """
    results: dict[int, dict] = {}

    async def _one(agent: "Agent"):
        memories = memories_map.get(agent.agent_id, [])
        plan     = plans_map.get(agent.agent_id, "")
        prompt   = _build_action_prompt(agent, world_state, memories, plan)
        raw      = await _single_call(prompt, max_tokens=200)
        parsed   = _parse_action(raw)
        if parsed:
            results[agent.agent_id] = parsed

    for i in range(0, len(agents), TIER2_BATCH_SIZE):
        chunk = agents[i: i + TIER2_BATCH_SIZE]
        await asyncio.gather(*[_one(a) for a in chunk], return_exceptions=True)

    return results


async def batch_plan(
    agents: list["Agent"],
    world_state: dict,
) -> dict[int, str]:
    """Generate daily plan text for each tier-2 agent."""
    plans: dict[int, str] = {}

    async def _one(agent: "Agent"):
        prompt = _build_plan_prompt(agent, world_state)
        text   = await _single_call(prompt, max_tokens=120)
        plans[agent.agent_id] = text.strip()

    for i in range(0, len(agents), TIER2_BATCH_SIZE):
        chunk = agents[i: i + TIER2_BATCH_SIZE]
        await asyncio.gather(*[_one(a) for a in chunk], return_exceptions=True)

    return plans


async def generate_reflection(agent: "Agent", memories: list[dict]) -> str:
    """Generate a reflection insight for a tier-2 agent."""
    mem_lines = "\n".join(
        f"  [Tick {m['tick']}] {m['event']}  (importance {m['importance']}/10)"
        for m in memories
    )
    prompt = (
        f"You are {agent.name}, {agent.role}.\n\n"
        f"Review your memories:\n{mem_lines}\n\n"
        f"In 1-2 sentences, synthesize: what pattern do you notice, "
        f"what concerns you most, or what you will do differently? "
        f"Stay in character as {agent.name}."
    )
    return (await _single_call(prompt, max_tokens=150)).strip()

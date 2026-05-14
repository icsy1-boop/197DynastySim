# sim/onit/interaction_engine.py
# Generates LLM-driven conversations between co-located agents (Smallville mechanic).
# Each interaction produces memories for both agents and may shift world state.

import asyncio, sqlite3
from datetime import datetime, timezone
from openai import AsyncOpenAI
from .constants import MODEL_NAME, VLLM_BASE_URL, DB_PATH
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .agent_loader import Agent

_client = AsyncOpenAI(base_url=VLLM_BASE_URL, api_key="dummy")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_interaction_prompt(
    a: "Agent", b: "Agent",
    location: str, world_state: dict,
) -> str:
    return (
        f"Two people meet at {location} in Mabuhay Province.\n\n"
        f"Person A: {a.name}, {a.role}. "
        f"Goals: {' | '.join(a.goals[:2])}. "
        f"Traits: integrity={a.integrity:.2f}, greed={a.greed:.2f}. "
        f"Family: {a.family_id or 'independent'}.\n"
        f"Person B: {b.name}, {b.role}. "
        f"Goals: {' | '.join(b.goals[:2])}. "
        f"Traits: integrity={b.integrity:.2f}, greed={b.greed:.2f}. "
        f"Family: {b.family_id or 'independent'}.\n\n"
        f"World: dynasty={world_state['dynasty_score']:.0f}  "
        f"scrutiny={world_state['scrutiny']:.0f}  "
        f"election_in={world_state['election_in']}\n\n"
        f"Describe their brief encounter in exactly 2 lines:\n"
        f"LINE1: From {a.name}'s perspective — what they said/noticed/agreed or disagreed about.\n"
        f"LINE2: From {b.name}'s perspective — the same encounter from their view.\n"
        f"Be specific and politically realistic. No labels, just the 2 lines."
    )


# World state effects when specific role pairs interact
_INTERACTION_EFFECTS: dict[frozenset, dict] = {
    frozenset({"journalist", "governor"}):       {"scrutiny": +5.0},
    frozenset({"journalist", "mayor"}):          {"scrutiny": +5.0},
    frozenset({"contractor", "governor"}):       {"corruption": +3.0, "family_wealth": +2.0},
    frozenset({"contractor", "mayor"}):          {"corruption": +3.0, "family_wealth": +2.0},
    frozenset({"auditor", "contractor"}):        {"scrutiny": +8.0, "corruption": -2.0},
    frozenset({"police", "contractor"}):         {"scrutiny": +4.0},
    frozenset({"barangay_captain", "governor"}): {"dynasty_score": +1.0},
    frozenset({"board_member", "governor"}):     {"dynasty_score": +1.0},
    frozenset({"vice_mayor", "mayor"}):          {"dynasty_score": +1.0},
}


def _apply_interaction_effects(a: "Agent", b: "Agent", world_state: dict) -> dict:
    """Return delta dict for world state based on who interacted."""
    key     = frozenset({a.role, b.role})
    effects = _INTERACTION_EFFECTS.get(key, {})

    # Cross-family interactions dampen effects; same-family boost them
    same_family = (a.family_id and b.family_id and a.family_id == b.family_id)
    factor      = 1.3 if same_family else 1.0

    return {k: v * factor for k, v in effects.items()}


def _write_memory(conn, agent: "Agent", tick: int, event: str, importance: int):
    conn.execute(
        "INSERT INTO agent_memory (agent_name, tick, event, importance, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (agent.agent_key or agent.name.lower().split()[0],
         tick, event, importance, _now()),
    )


async def run_interactions(
    pairs:       list[tuple["Agent", "Agent", str]],
    world_state: dict,
    tick:        int,
) -> dict[str, float]:
    """
    Generate all interactions for this tick.
    Returns accumulated world state deltas.
    """
    total_deltas: dict[str, float] = {}

    async def _one(a: "Agent", b: "Agent", location: str):
        prompt = _build_interaction_prompt(a, b, location, world_state)
        try:
            resp = await _client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.75,
            )
            text   = (resp.choices[0].message.content or "").strip()
            lines  = [l.strip() for l in text.split("\n") if l.strip()]
            mem_a  = lines[0] if lines     else f"Met {b.name} at {location}."
            mem_b  = lines[1] if len(lines) > 1 else f"Met {a.name} at {location}."
        except Exception:
            mem_a = f"Met {b.name} at {location}."
            mem_b = f"Met {a.name} at {location}."

        # Write memories for both
        conn = sqlite3.connect(DB_PATH)
        importance = 6 if (a.tier == 1 or b.tier == 1) else 4
        _write_memory(conn, a, tick, mem_a, importance)
        _write_memory(conn, b, tick, mem_b, importance)
        conn.commit()
        conn.close()

        # Accumulate world state effects
        deltas = _apply_interaction_effects(a, b, world_state)
        for k, v in deltas.items():
            total_deltas[k] = total_deltas.get(k, 0.0) + v

        print(f"  ↔ {a.name} × {b.name} @ {location}")

    await asyncio.gather(*[_one(a, b, loc) for a, b, loc in pairs],
                         return_exceptions=True)

    return total_deltas


def apply_interaction_deltas(deltas: dict[str, float]):
    """Write accumulated interaction effects to world state DB."""
    if not deltas:
        return
    conn    = sqlite3.connect(DB_PATH)
    row     = conn.execute(
        "SELECT * FROM world_state ORDER BY tick DESC LIMIT 1"
    ).fetchone()
    cols    = [d[0] for d in conn.execute(
        "SELECT * FROM world_state LIMIT 0"
    ).description]
    state   = dict(zip(cols, row))
    for k, v in deltas.items():
        if k in state and isinstance(state[k], (int, float)):
            state[k] = max(0.0, min(100.0, state[k] + v))
    state["updated_at"] = _now()
    conn.execute("""
        UPDATE world_state SET
          dynasty_score=:dynasty_score, corruption=:corruption,
          scrutiny=:scrutiny, civic_trust=:civic_trust, unrest=:unrest,
          family_wealth=:family_wealth, updated_at=:updated_at
        WHERE tick=(SELECT MAX(tick) FROM world_state)
    """, state)
    conn.commit()
    conn.close()

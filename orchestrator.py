# orchestrator.py
# Smallville-equivalent simulation loop for the Tatlonghari dynasty.
#
# Each tick runs 6 phases (matching Smallville's architecture):
#   PLAN      — agents set daily intentions (every PLAN_INTERVAL ticks)
#   MOVE      — agents update locations (day/night movement)
#   ACT       — tier-1 via OnIt A2A, tier-2 via vLLM batch, tier-3 rule-based
#   INTERACT  — co-located agents generate conversations → memories
#   OBSERVE   — write episodic memories + advance world tick
#   REFLECT   — importance-triggered synthesis (when accum >= REFLECT_THRESHOLD)
#
# Prerequisites:
#   python mcp_servers/dynasty_mcp_server.py
#   bash start_agents.sh   (starts all 10 OnIt agents)
#   python orchestrator.py

import asyncio, json, sqlite3, httpx
from datetime import datetime, timezone

from sim.onit.agent_loader    import load_agents, agents_by_tier, Agent
from sim.onit.vllm_client     import (batch_act, batch_plan,
                                       generate_reflection, _client)
from sim.onit.location_engine import (init_location_table, update_locations,
                                       find_interaction_pairs)
from sim.onit.interaction_engine import run_interactions, apply_interaction_deltas
from sim.onit.constants       import (DB_PATH, CSV_PATH, MODEL_NAME,
                                       REFLECT_THRESHOLD, PLAN_INTERVAL,
                                       TIER1_CONFIG)

# ── Config ────────────────────────────────────────────────────────────────────

NUM_TICKS   = 10
TICK_PAUSE  = 2   # seconds between ticks
LOG_DIR     = "logs"
_SESSION_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
_LOG_PATH   = f"{LOG_DIR}/session_{_SESSION_ID}.jsonl"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_world_state() -> dict:
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT * FROM world_state ORDER BY tick DESC LIMIT 1"
    ).fetchone()
    cols = [d[0] for d in conn.execute(
        "SELECT * FROM world_state LIMIT 0"
    ).description]
    conn.close()
    return dict(zip(cols, row))


def get_memories(agent_key: str, current_tick: int, n: int = 5) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT tick, event, importance FROM agent_memory "
        "WHERE agent_name=? ORDER BY tick DESC LIMIT 60",
        (agent_key,),
    ).fetchall()
    conn.close()
    scored = [(imp * (0.9 ** (current_tick - t)), t, ev, imp)
              for t, ev, imp in rows]
    scored.sort(reverse=True)
    return [{"tick": t, "event": e, "importance": i}
            for _, t, e, i in scored[:n]]


def get_plan(agent_key: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT plan_text FROM agent_plans WHERE agent_name=?",
        (agent_key,),
    ).fetchone()
    conn.close()
    return row[0] if row else ""


def write_action(tick: int, agent_id: int | None, agent_name: str,
                  tier: int, action: str, params: dict, reasoning: str):
    """Log one agent action to agent_actions table and JSONL session log."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO agent_actions "
        "(tick, agent_id, agent_name, agent_tier, action, params, reasoning, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (tick, agent_id, agent_name, tier,
         action, json.dumps(params), reasoning, _now()),
    )
    conn.commit()
    conn.close()
    # JSONL session log
    import os
    os.makedirs(LOG_DIR, exist_ok=True)
    record = {
        "ts": _now(), "tick": tick, "agent": agent_name,
        "tier": tier, "action": action, "params": params, "reasoning": reasoning,
    }
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def write_memory(agent_key: str, tick: int, event: str, importance: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO agent_memory (agent_name, tick, event, importance, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (agent_key, tick, event, max(1, min(10, importance)), _now()),
    )
    conn.commit()
    conn.close()


def advance_tick():
    conn  = sqlite3.connect(DB_PATH)
    row   = conn.execute(
        "SELECT * FROM world_state ORDER BY tick DESC LIMIT 1"
    ).fetchone()
    cols  = [d[0] for d in conn.execute(
        "SELECT * FROM world_state LIMIT 0"
    ).description]
    s     = dict(zip(cols, row))
    conn.execute("""
        INSERT INTO world_state
          (tick, dynasty_score, corruption, scrutiny, civic_trust, unrest,
           family_wealth, election_in, recent_events, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        s["tick"] + 1,
        s["dynasty_score"],
        s["corruption"],
        s["scrutiny"],
        max(0.0, s["civic_trust"] - 1.0),
        s["unrest"],
        s["family_wealth"],
        max(0, s["election_in"] - 1),
        "",
        _now(),
    ))
    conn.commit()
    conn.close()


# ── Phase 1: PLAN ─────────────────────────────────────────────────────────────

def _build_plan_prompt_t1(agent: Agent, world_state: dict) -> str:
    return (
        f"You are {agent.name}, {agent.role}.\n"
        f"Goals: {' | '.join(agent.goals)}\n\n"
        f"World: dynasty={world_state['dynasty_score']:.0f}  "
        f"scrutiny={world_state['scrutiny']:.0f}  "
        f"election_in={world_state['election_in']}\n\n"
        f"In 2 sentences, state your plan for today. Be specific.\n"
        f"Then call make_plan('{agent.agent_key}', '<your plan>')."
    )


async def _send_a2a(port: int, text: str) -> dict:
    payload = {
        "jsonrpc": "2.0", "id": 1,
        "method":  "message/send",
        "params":  {
            "message": {
                "role":      "user",
                "parts":     [{"kind": "text", "text": text}],
                "messageId": "plan",
            }
        },
    }
    async with httpx.AsyncClient(timeout=90.0) as c:
        r = await c.post(f"http://localhost:{port}", json=payload)
        r.raise_for_status()
        return r.json()


async def run_plan_phase(t1_agents: list[Agent], t2_agents: list[Agent],
                          world_state: dict):
    print("  [PLAN]")
    # Tier 1 — send via A2A
    t1_coros = [
        _send_a2a(a.a2a_port, _build_plan_prompt_t1(a, world_state))
        for a in t1_agents
    ]
    await asyncio.gather(*t1_coros, return_exceptions=True)

    # Tier 2 — direct vLLM batch
    plans = await batch_plan(t2_agents, world_state)
    conn  = sqlite3.connect(DB_PATH)
    tick  = world_state["tick"]
    for agent_id, plan_text in plans.items():
        conn.execute(
            "INSERT OR REPLACE INTO agent_plans "
            "(agent_name, tick, plan_text, updated_at) VALUES (?,?,?,?)",
            (str(agent_id), tick, plan_text, _now()),
        )
    conn.commit()
    conn.close()


# ── Phase 3: ACT ──────────────────────────────────────────────────────────────

def _build_t1_task(agent: Agent, world_state: dict,
                   memories: list[dict], plan: str) -> str:
    mem_block  = ""
    if memories:
        lines     = [f"  [Tick {m['tick']}] {m['event']}  (importance {m['importance']}/10)"
                     for m in memories]
        mem_block = "YOUR MEMORIES:\n" + "\n".join(lines) + "\n\n"

    plan_block = f"TODAY'S PLAN: {plan}\n\n" if plan else ""

    return (
        f"{mem_block}"
        f"{plan_block}"
        f"WORLD STATE — Tick {world_state['tick']}:\n"
        f"  Dynasty: {world_state['dynasty_score']:.1f}  "
        f"Corruption: {world_state['corruption']:.1f}  "
        f"Scrutiny: {world_state['scrutiny']:.1f}\n"
        f"  Trust: {world_state['civic_trust']:.1f}  "
        f"Unrest: {world_state['unrest']:.1f}  "
        f"Wealth: {world_state['family_wealth']:.1f}\n"
        f"  Election in: {world_state['election_in']} ticks\n"
        f"  Events: {world_state.get('recent_events','')}\n\n"
        f"You are at {agent.current_location}. Choose your action."
    )


async def run_act_phase(
    t1_agents:    list[Agent],
    t2_agents:    list[Agent],
    t3_agents:    list[Agent],
    world_state:  dict,
) -> dict[str, str]:
    """Returns {agent_key_or_id: response_text}"""
    print("  [ACT]")
    tick     = world_state["tick"]
    responses: dict[str, str] = {}

    # Tier 1 — OnIt A2A (parallel)
    async def _t1_act(a: Agent):
        memories = get_memories(a.agent_key, tick)
        plan     = get_plan(a.agent_key)
        task     = _build_t1_task(a, world_state, memories, plan)
        try:
            result = await _send_a2a(a.a2a_port, task)
            parts  = (result.get("result", {})
                            .get("status", {})
                            .get("message", {})
                            .get("parts", []))
            text   = " ".join(p.get("text", "") for p in parts)
            responses[a.agent_key] = text
            write_action(
                tick=world_state["tick"],
                agent_id=a.agent_id,
                agent_name=a.name,
                tier=1,
                action="onit_response",
                params={},
                reasoning=text[:300],
            )
            print(f"    ✓ {a.name}: {text[:100]}...")
        except Exception as e:
            print(f"    ✗ {a.name}: {e}")

    await asyncio.gather(*[_t1_act(a) for a in t1_agents], return_exceptions=True)

    # Tier 2 — vLLM batch
    mem_map  = {a.agent_id: get_memories(str(a.agent_id), tick) for a in t2_agents}
    plan_map = {a.agent_id: get_plan(str(a.agent_id)) for a in t2_agents}
    t2_acts  = await batch_act(t2_agents, world_state, mem_map, plan_map)

    # Apply tier-2 actions to world state via DB (map JSON → effects)
    _apply_t2_actions(t2_acts, t2_agents)

    for agent_id, action in t2_acts.items():
        reasoning = action.get("reasoning", "")
        responses[str(agent_id)] = reasoning
        a = next((x for x in t2_agents if x.agent_id == agent_id), None)
        write_action(
            tick=world_state["tick"],
            agent_id=agent_id,
            agent_name=a.name if a else str(agent_id),
            tier=2,
            action=action.get("action", "unknown"),
            params=action.get("params", {}),
            reasoning=reasoning,
        )

    # Tier 3 — rule-based satisfaction update
    _tier3_act(t3_agents, world_state)

    return responses


def _apply_t2_actions(actions: dict[int, dict], agents: list[Agent]):
    """Map tier-2 parsed action JSON to world state DB updates."""
    conn  = sqlite3.connect(DB_PATH)
    row   = conn.execute(
        "SELECT * FROM world_state ORDER BY tick DESC LIMIT 1"
    ).fetchone()
    cols  = [d[0] for d in conn.execute(
        "SELECT * FROM world_state LIMIT 0"
    ).description]
    state = dict(zip(cols, row))

    agent_map = {a.agent_id: a for a in agents}
    events    = []

    for agent_id, action in actions.items():
        a    = agent_map.get(agent_id)
        name = a.name if a else str(agent_id)
        act  = action.get("action", "")
        p    = action.get("params", {})

        if act == "lay_low":
            state["scrutiny"] = max(0, state["scrutiny"] - 8)
            events.append(f"{name} laid low.")
        elif act == "secure_contract":
            v = float(p.get("value", 5))
            state["family_wealth"] = min(100, state["family_wealth"] + v * 0.4)
            state["corruption"]    = min(100, state["corruption"]    + 6)
            state["scrutiny"]      = min(100, state["scrutiny"]      + 8)
            events.append(f"{name} secured contract.")
        elif act == "vote_ordinance":
            if p.get("stance", "").lower() == "yes":
                state["civic_trust"]  = min(100, state["civic_trust"]  + 2)
                state["corruption"]   = max(0,   state["corruption"]   - 1)
            events.append(f"{name} voted {p.get('stance','?')} on {p.get('bill','bill')}.")
        elif act == "bribe_official":
            state["corruption"] = min(100, state["corruption"] + 10)
            state["scrutiny"]   = min(100, state["scrutiny"]   + 14)
            events.append(f"{name} bribed {p.get('official_name','official')}.")
        elif act == "publish_story":
            state["scrutiny"]      = min(100, state["scrutiny"]      + 18)
            state["civic_trust"]   = min(100, state["civic_trust"]   + 6)
            state["dynasty_score"] = max(0,   state["dynasty_score"] - 4)
            events.append(f"{name} published story about {p.get('target','?')}.")
        elif act == "suppress_rival":
            state["dynasty_score"] = min(100, state["dynasty_score"] + 5)
            state["scrutiny"]      = min(100, state["scrutiny"]      + 12)
            events.append(f"{name} suppressed {p.get('rival_name','rival')}.")

    prev = (state.get("recent_events") or "").strip(" |")
    state["recent_events"] = (prev + " | " + " | ".join(events)).strip(" |")[-500:]
    state["updated_at"]    = _now()

    conn.execute("""
        UPDATE world_state SET
          dynasty_score=:dynasty_score, corruption=:corruption,
          scrutiny=:scrutiny, civic_trust=:civic_trust, unrest=:unrest,
          family_wealth=:family_wealth, recent_events=:recent_events,
          updated_at=:updated_at
        WHERE tick=(SELECT MAX(tick) FROM world_state)
    """, state)
    conn.commit()
    conn.close()


def _tier3_act(agents: list[Agent], world_state: dict):
    """Rule-based: update satisfaction; aggregate feeds back into civic_trust."""
    trust_factor  = (world_state["civic_trust"] - 50) * 0.01
    unrest_factor = -world_state["unrest"] * 0.005
    for a in agents:
        a.satisfaction = max(0.0, min(100.0,
            a.satisfaction + trust_factor + unrest_factor
            + (a.income_per_day / 10000 - 0.5) * 0.1
        ))

    avg_sat = sum(a.satisfaction for a in agents) / max(1, len(agents))
    # Aggregate satisfaction nudges civic_trust
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE world_state SET civic_trust = MAX(0, MIN(100, civic_trust + ?))"
        " WHERE tick=(SELECT MAX(tick) FROM world_state)",
        ((avg_sat - 50) * 0.02,),
    )
    conn.commit()
    conn.close()


# ── Phase 5: OBSERVE ──────────────────────────────────────────────────────────

_SCRUTINY_WATCHERS = {"gilberto", "isadora", "noel", "esperanza"}
_DYNASTY_WATCHERS  = {"gilberto", "isadora", "esperanza"}
_WEALTH_WATCHERS   = {"nicanor",  "noel",    "gilberto"}


def record_tick_memories(
    tick:      int,
    prev:      dict,
    curr:      dict,
    responses: dict[str, str],
    agents:    list[Agent],
):
    scrutiny_delta = curr["scrutiny"]      - prev["scrutiny"]
    dynasty_delta  = curr["dynasty_score"] - prev["dynasty_score"]
    wealth_delta   = curr["family_wealth"] - prev["family_wealth"]
    recent         = (curr.get("recent_events") or "").strip(" |")
    base           = 5
    if curr["scrutiny"] >= 70 or curr["election_in"] <= 1:
        base = 8
    elif abs(scrutiny_delta) >= 15 or abs(dynasty_delta) >= 5:
        base = 7

    for a in agents:
        if a.tier > 2:
            continue
        key   = a.agent_key or str(a.agent_id)
        parts = []

        action_text = responses.get(key, "").strip()
        if action_text:
            parts.append(f"I acted: {action_text[:120]}")
        if abs(scrutiny_delta) >= 10 and key in _SCRUTINY_WATCHERS:
            d = "rose" if scrutiny_delta > 0 else "fell"
            parts.append(f"Scrutiny {d} {abs(scrutiny_delta):.0f}pts to {curr['scrutiny']:.0f}")
        if dynasty_delta <= -3 and key in _DYNASTY_WATCHERS:
            parts.append(f"Dynasty score dropped to {curr['dynasty_score']:.0f}")
        if wealth_delta >= 5 and key in _WEALTH_WATCHERS:
            parts.append(f"Family wealth grew to {curr['family_wealth']:.0f}")
        if curr["election_in"] == 1:
            parts.append("ELECTION IS ONE TICK AWAY")
        if not parts and recent:
            parts.append(recent[:200])
        if not parts:
            continue

        importance = base
        if key == "esperanza" and dynasty_delta <= -3:
            importance = 9
        if key in ("gilberto", "noel") and curr["scrutiny"] >= 65:
            importance = min(10, importance + 1)

        write_memory(key, tick, ". ".join(parts), importance)

        # Accumulate importance for reflection trigger
        for a2 in agents:
            if (a2.agent_key or str(a2.agent_id)) == key:
                a2.importance_accum += importance
                break


# ── Phase 6: REFLECT ──────────────────────────────────────────────────────────

async def run_reflect_phase(
    t1_agents: list[Agent],
    t2_agents: list[Agent],
    tick:      int,
):
    """Importance-triggered reflection — Smallville style."""
    print("  [REFLECT]")

    # Tier 1 — send reflection via A2A
    async def _t1_reflect(a: Agent):
        memories = get_memories(a.agent_key, tick, n=8)
        if not memories:
            return
        mem_lines = "\n".join(
            f"  [Tick {m['tick']}] {m['event']}  (importance {m['importance']}/10)"
            for m in memories
        )
        prompt = (
            f"You are {a.name}, {a.role}.\n\n"
            f"Review your memories:\n{mem_lines}\n\n"
            f"In 1-2 sentences, synthesize: what pattern do you see, "
            f"what concerns you most, or what you will do differently.\n"
            f"Call remember('{a.agent_key}', <your insight>, 9)."
        )
        try:
            await _send_a2a(a.a2a_port, prompt)
            a.importance_accum = 0.0
            print(f"    ↺ {a.name} reflected")
        except Exception as e:
            print(f"    ↺ {a.name} reflection failed: {e}")

    # Tier 2 — direct vLLM
    async def _t2_reflect(a: Agent):
        memories = get_memories(str(a.agent_id), tick, n=8)
        if not memories:
            return
        insight = await generate_reflection(a, memories)
        if insight:
            write_memory(str(a.agent_id), tick, f"REFLECTION: {insight}", 9)
        a.importance_accum = 0.0
        print(f"    ↺ {a.name} reflected (tier-2)")

    t1_due = [a for a in t1_agents if a.importance_accum >= REFLECT_THRESHOLD]
    t2_due = [a for a in t2_agents if a.importance_accum >= REFLECT_THRESHOLD]

    if not t1_due and not t2_due:
        return

    await asyncio.gather(
        *[_t1_reflect(a) for a in t1_due],
        *[_t2_reflect(a) for a in t2_due],
        return_exceptions=True,
    )


# ── Main loop ─────────────────────────────────────────────────────────────────

async def main():
    init_location_table()
    agents             = load_agents(CSV_PATH)
    t1, t2, t3        = agents_by_tier(agents)

    print(f"\nStarting Smallville-equivalent simulation")
    print(f"Tier 1 (OnIt):       {len(t1)} agents")
    print(f"Tier 2 (vLLM batch): {len(t2)} agents")
    print(f"Tier 3 (rule-based): {len(t3)} agents\n")

    for tick_num in range(NUM_TICKS):
        sep   = "=" * 60
        state = get_world_state()
        print(f"\n{sep}\nTICK {tick_num}  |  "
              f"dynasty={state['dynasty_score']:.0f}  "
              f"corruption={state['corruption']:.0f}  "
              f"scrutiny={state['scrutiny']:.0f}  "
              f"trust={state['civic_trust']:.0f}  "
              f"election_in={state['election_in']}\n{sep}")

        # ── 1. PLAN (every PLAN_INTERVAL ticks)
        if tick_num % PLAN_INTERVAL == 0:
            await run_plan_phase(t1, t2, state)

        # ── 2. MOVE
        update_locations(agents, tick_num)

        # ── 3. ACT
        responses = await run_act_phase(t1, t2, t3, state)

        # ── 4. INTERACT
        pairs   = find_interaction_pairs(agents)
        if pairs:
            print(f"  [INTERACT] {len(pairs)} pair(s)")
            deltas  = await run_interactions(pairs, state, tick_num)
            apply_interaction_deltas(deltas)

        # ── 5. OBSERVE
        advance_tick()
        new_state = get_world_state()
        record_tick_memories(tick_num, state, new_state, responses, agents)

        # ── 6. REFLECT (importance-triggered)
        await run_reflect_phase(t1, t2, tick_num)

        print(f"Tick {tick_num} complete.")
        if tick_num < NUM_TICKS - 1:
            await asyncio.sleep(TICK_PAUSE)

    print("\nSimulation complete.")
    print(json.dumps(get_world_state(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())

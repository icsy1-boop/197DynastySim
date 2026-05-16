# mcp_servers/dynasty_mcp_server.py
# Tatlonghari Dynasty MCP Server — world state + role-scoped action tools.
# Run: python mcp_servers/dynasty_mcp_server.py
# OnIt connects via: http://127.0.0.1:18300/dynasty

import sqlite3, json
from fastmcp import FastMCP
from datetime import datetime, timezone

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

DB  = "dynasty_world.db"
mcp = FastMCP("DynastyMCPServer")

# Initial world state reflects Tatlonghari dominance at sim start.
_SEED = {
    "dynasty_score": 70.0,   # % of offices held by Tatlonghari family
    "corruption":    45.0,   # normalized corruption index
    "scrutiny":      25.0,   # media/audit pressure on dynasty
    "civic_trust":   55.0,   # citizen trust in government
    "unrest":        20.0,   # public unrest
    "family_wealth": 75.0,   # normalized family wealth
    "election_in":    6,     # ticks to next election
}


def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name  TEXT    NOT NULL,
            tick        INTEGER NOT NULL,
            event       TEXT    NOT NULL,
            importance  INTEGER DEFAULT 5 CHECK(importance BETWEEN 1 AND 10),
            created_at  TEXT    NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mem_agent "
        "ON agent_memory(agent_name, tick)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_locations (
            agent_id   INTEGER PRIMARY KEY,
            agent_name TEXT    NOT NULL,
            location   TEXT    NOT NULL,
            updated_at TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_plans (
            agent_name TEXT    PRIMARY KEY,
            tick       INTEGER NOT NULL,
            plan_text  TEXT    NOT NULL,
            updated_at TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_actions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tick        INTEGER NOT NULL,
            agent_id    INTEGER,
            agent_name  TEXT    NOT NULL,
            agent_tier  INTEGER DEFAULT 1,
            action      TEXT    NOT NULL,
            params      TEXT,
            reasoning   TEXT,
            created_at  TEXT    NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_actions_tick "
        "ON agent_actions(tick)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS election_results (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            tick           INTEGER NOT NULL,
            calendar_year  INTEGER DEFAULT 2020,
            candidate_id   INTEGER,
            candidate_name TEXT    NOT NULL,
            role           TEXT,
            vote_score     REAL    DEFAULT 0.0,
            won            INTEGER DEFAULT 0,
            family_id      TEXT,
            created_at     TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_state (
            tick            INTEGER PRIMARY KEY,
            dynasty_score   REAL    DEFAULT 70.0,
            corruption      REAL    DEFAULT 45.0,
            scrutiny        REAL    DEFAULT 25.0,
            civic_trust     REAL    DEFAULT 55.0,
            unrest          REAL    DEFAULT 20.0,
            family_wealth   REAL    DEFAULT 75.0,
            election_in     INTEGER DEFAULT 6,
            recent_events   TEXT    DEFAULT '',
            updated_at      TEXT
        )
    """)
    if not conn.execute("SELECT 1 FROM world_state WHERE tick=0").fetchone():
        conn.execute(
            """INSERT INTO world_state VALUES
               (0, :dynasty_score, :corruption, :scrutiny, :civic_trust,
                :unrest, :family_wealth, :election_in,
                'Tatlonghari dynasty in power. Gilberto governs.', :ts)""",
            {**_SEED, "ts": _now()},
        )
        conn.commit()
    conn.close()


def _latest(conn) -> dict:
    row  = conn.execute(
        "SELECT * FROM world_state ORDER BY tick DESC LIMIT 1"
    ).fetchone()
    cols = [d[0] for d in conn.execute(
        "SELECT * FROM world_state LIMIT 0"
    ).description]
    return dict(zip(cols, row))


def _update(conn, event: str, **deltas):
    """Apply float deltas (clamped 0-100) and append event string."""
    s = _latest(conn)
    for k, v in deltas.items():
        if k in s and isinstance(v, float):
            s[k] = max(0.0, min(100.0, s[k] + v))
        elif k in s:
            s[k] = v
    prev = (s.get("recent_events") or "").strip(" |")
    s["recent_events"] = (prev + " | " + event).strip(" |")[-500:]
    s["updated_at"]    = _now()
    conn.execute("""
        UPDATE world_state SET
          dynasty_score=:dynasty_score, corruption=:corruption,
          scrutiny=:scrutiny, civic_trust=:civic_trust, unrest=:unrest,
          family_wealth=:family_wealth, election_in=:election_in,
          recent_events=:recent_events, updated_at=:updated_at
        WHERE tick=(SELECT MAX(tick) FROM world_state)
    "", s)
    conn.commit()


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_world_state() -> str:
    """Get the current world state. Call this first each tick."""
    conn  = sqlite3.connect(DB)
    state = _latest(conn)
    conn.close()
    return json.dumps(state, indent=2)


@mcp.tool()
def lay_low() -> str:
    """
    Lie low this tick — no aggressive moves.
    Reduces scrutiny by 10. REQUIRED when scrutiny >= 70.
    """
    conn = sqlite3.connect(DB)
    _update(conn, "Agent laid low this tick.", scrutiny=-10.0)
    conn.close()
    return "Laid low. Scrutiny -10."


@mcp.tool()
def secure_contract(agency: str, value: float) -> str:
    """
    [GOVERNOR / CONTRACTOR] Secure a government infrastructure contract.
    Raises family_wealth and corruption; increases scrutiny.
    agency: government agency (DPWH, DepEd, DOH, DILG, etc.)
    value: contract value 1-20 (scale)
    """
    conn = sqlite3.connect(DB)
    _update(conn, f"Contract secured with {agency} (scale={value:.0f}).",
            family_wealth=+value * 0.5, corruption=+8.0, scrutiny=+10.0)
    conn.close()
    return (f"Contract secured with {agency}. "
            f"Family wealth +{value*0.5:.1f}, corruption +8, scrutiny +10.")


@mcp.tool()
def suppress_rival(rival_name: str) -> str:
    """
    [GOVERNOR / MAYOR] Suppress a political rival by leveraging government power.
    Raises dynasty_score; triggers scrutiny and unrest spikes.
    rival_name: full name of the rival candidate or official
    """
    conn = sqlite3.connect(DB)
    _update(conn, f"Rival {rival_name} suppressed.",
            dynasty_score=+6.0, scrutiny=+15.0, unrest=+5.0)
    conn.close()
    return f"Rival {rival_name} suppressed. Dynasty +6, scrutiny +15, unrest +5."


@mcp.tool()
def place_ally(ally_name: str, position: str) -> str:
    """
    [GOVERNOR / MAYOR] Install a family ally in a government position.
    Grows dynasty_score; costs family wealth; mild scrutiny increase.
    ally_name: name of the family member or ally
    position: target position (e.g., 'OIC Director DPWH', 'Board Secretary')
    """
    conn = sqlite3.connect(DB)
    _update(conn, f"{ally_name} placed as {position}.",
            dynasty_score=+5.0, family_wealth=-3.0, scrutiny=+7.0)
    conn.close()
    return f"{ally_name} placed as {position}. Dynasty +5, wealth -3, scrutiny +7."


@mcp.tool()
def vote_ordinance(bill: str, stance: str) -> str:
    """
    [BOARD MEMBER / COUNCILOR] Vote on a bill or provincial ordinance.
    bill: name or short description of the bill
    stance: 'yes', 'no', or 'abstain'
    """
    conn  = sqlite3.connect(DB)
    sl    = stance.lower()
    event = f"Voted {stance.upper()} on '{bill}'."
    if sl == "yes":
        _update(conn, event, civic_trust=+3.0, corruption=-2.0)
        result = f"Voted YES on '{bill}'. Civic trust +3, corruption -2."
    elif sl == "no":
        _update(conn, event, corruption=+2.0)
        result = f"Voted NO on '{bill}'. Corruption +2."
    else:
        _update(conn, event)
        result = f"Abstained on '{bill}'."
    conn.close()
    return result


@mcp.tool()
def bribe_official(official_name: str, amount: float) -> str:
    """
    [CONTRACTOR] Bribe a government official to secure a contract or permit.
    High risk: large corruption and scrutiny spikes.
    official_name: name of the official
    amount: bribe scale 1-10
    """
    conn = sqlite3.connect(DB)
    _update(conn, f"{official_name} bribed (scale={amount:.0f}).",
            corruption=+12.0, scrutiny=+18.0, family_wealth=+amount * 0.8)
    conn.close()
    return (f"{official_name} bribed. "
            f"Corruption +12, scrutiny +18, family wealth +{amount*0.8:.1f}.")


@mcp.tool()
def publish_story(target: str, allegation: str) -> str:
    """
    [JOURNALIST] Publish an investigative story exposing corruption.
    Raises scrutiny and civic_trust; reduces dynasty_score; triggers unrest.
    target: name of the official or family member being exposed
    allegation: one-sentence summary of the allegation
    """
    conn = sqlite3.connect(DB)
    _update(conn, f"Story published: {target} — {allegation[:80]}.",
            scrutiny=+20.0, civic_trust=+8.0, dynasty_score=-5.0, unrest=+3.0)
    conn.close()
    return (f"Story published about {target}. "
            f"Scrutiny +20, civic trust +8, dynasty score -5.")


@mcp.tool()
def advance_tick() -> str:
    """
    [ORCHESTRATOR ONLY] Advance the simulation by one tick.
    Call ONLY after all agents have acted for this tick.
    """
    conn    = sqlite3.connect(DB)
    current = _latest(conn)
    new_tick = current["tick"] + 1
    tte      = max(0, current["election_in"] - 1)
    conn.execute("""
        INSERT INTO world_state
          (tick, dynasty_score, corruption, scrutiny, civic_trust, unrest,
           family_wealth, election_in, recent_events, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        new_tick,
        current["dynasty_score"],
        current["corruption"],
        current["scrutiny"],
        max(0.0, current["civic_trust"] - 1.0),  # trust erodes each tick
        current["unrest"],
        current["family_wealth"],
        tte,
        "",
        _now(),
    ))
    conn.commit()
    conn.close()
    return f"Tick advanced to {new_tick}. Election in {tte} ticks."


# ── Location + planning tools ─────────────────────────────────────────────────

@mcp.tool()
def get_nearby_agents(location: str) -> str:
    """
    See who else is at your current location.
    location: zone name (e.g. 'capitol', 'munhall', 'market')
    """
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT agent_name FROM agent_locations WHERE location=?",
        (location,),
    ).fetchall()
    conn.close()
    names = [r[0] for r in rows]
    if not names:
        return f"No one else at {location}."
    return f"At {location}: {', '.join(names)}"


@mcp.tool()
def make_plan(agent_name: str, plan_text: str) -> str:
    """
    Record your plan for today.
    agent_name: your agent key
    plan_text: 1-3 sentences describing your intentions today
    """
    conn  = sqlite3.connect(DB)
    tick  = _latest(conn)["tick"]
    conn.execute(
        "INSERT OR REPLACE INTO agent_plans "
        "(agent_name, tick, plan_text, updated_at) VALUES (?,?,?,?)",
        (agent_name, tick, plan_text, _now()),
    )
    conn.commit()
    conn.close()
    return f"Plan recorded for {agent_name}."


@mcp.tool()
def get_my_plan(agent_name: str) -> str:
    """Retrieve your current daily plan."""
    conn = sqlite3.connect(DB)
    row  = conn.execute(
        "SELECT plan_text, tick FROM agent_plans WHERE agent_name=?",
        (agent_name,),
    ).fetchone()
    conn.close()
    if not row:
        return "No plan set yet."
    return f"[Tick {row[1]}] {row[0]}"


# ── Memory tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def recall(agent_name: str, n: int = 6) -> str:
    """
    Retrieve your most relevant memories, ranked by importance × recency.
    Call this at the start of each tick before choosing an action.
    agent_name: your agent key (e.g. 'gilberto', 'esperanza')
    n: how many memories to return
    """
    conn         = sqlite3.connect(DB)
    current_tick = _latest(conn)["tick"]
    rows         = conn.execute(
        "SELECT tick, event, importance FROM agent_memory "
        "WHERE agent_name=? ORDER BY tick DESC LIMIT 60",
        (agent_name,),
    ).fetchall()
    conn.close()

    if not rows:
        return f"No memories yet for {agent_name}."

    scored = []
    for tick, event, importance in rows:
        recency = 0.9 ** (current_tick - tick)
        scored.append((importance * recency, tick, event, importance))
    scored.sort(reverse=True)

    lines = [f"Memories for {agent_name} (importance × recency):"]
    for _, tick, event, imp in scored[:n]:
        lines.append(f"  [Tick {tick}] {event}  (importance {imp}/10)")
    return "\n".join(lines)


@mcp.tool()
def remember(agent_name: str, event: str, importance: int = 5) -> str:
    """
    Store a memory entry for this agent.
    agent_name: your agent key
    event: what happened or what you decided (1-2 sentences)
    importance: 1-10  (1=trivial, 5=routine, 8=significant, 10=life-changing)
    """
    conn = sqlite3.connect(DB)
    tick = _latest(conn)["tick"]
    conn.execute(
        "INSERT INTO agent_memory (agent_name, tick, event, importance, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (agent_name, tick, event, max(1, min(10, importance)),
         _now()),
    )
    conn.commit()
    conn.close()
    return f"Memory stored (tick {tick}, importance {importance})."


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("DynastyMCPServer starting at http://127.0.0.1:18300/dynasty")
    mcp.run(transport="sse", host="127.0.0.1", port=18200)

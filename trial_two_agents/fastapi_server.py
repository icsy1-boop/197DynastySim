# fastapi_server.py  —  Process D
# HTTP /state /metrics /agents /actions  +  WebSocket /ws  +  Phaser static /game
# Run: uvicorn fastapi_server:app --host 0.0.0.0 --port 5000 --reload
#
# Accessible from laptops at: http://dgx-ip:5000

import asyncio, csv, json, sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

DB_PATH  = "dynasty_world.db"
CSV_PATH = "barangay_agents.csv"


# ── DB helpers ────────────────────────────────────────────────────────────────


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables():
    """Create tables if the simulation hasn't started yet."""
    conn = _db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_state (
            tick INTEGER PRIMARY KEY, dynasty_score REAL, corruption REAL,
            scrutiny REAL, civic_trust REAL, unrest REAL, family_wealth REAL,
            election_in INTEGER, recent_events TEXT, updated_at TEXT
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tick INTEGER, agent_id INTEGER,
            agent_name TEXT, agent_tier INTEGER, action TEXT, params TEXT,
            reasoning TEXT, created_at TEXT
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS election_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tick INTEGER,
            calendar_year INTEGER, candidate_id INTEGER, candidate_name TEXT,
            role TEXT, vote_score REAL, won INTEGER, family_id TEXT, created_at TEXT
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, agent_name TEXT,
            tick INTEGER, event TEXT, importance INTEGER, created_at TEXT
        )""")
    conn.commit()
    conn.close()


def _world_state() -> dict | None:
    conn = _db()
    row = conn.execute(
        "SELECT * FROM world_state ORDER BY tick DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _world_history(n: int = 30) -> list[dict]:
    conn = _db()
    rows = conn.execute(
        "SELECT tick, dynasty_score, corruption, scrutiny, "
        "civic_trust, unrest, family_wealth "
        "FROM world_state ORDER BY tick DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def _recent_actions(n: int = 40) -> list[dict]:
    conn = _db()
    rows = conn.execute(
        "SELECT id, tick, agent_name, agent_tier, action, params, reasoning "
        "FROM agent_actions ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _actions_since(last_id: int) -> list[dict]:
    conn = _db()
    rows = conn.execute(
        "SELECT id, tick, agent_name, agent_tier, action, params, reasoning, created_at "
        "FROM agent_actions WHERE id > ? ORDER BY id ASC", (last_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _election_results() -> list[dict]:
    conn = _db()
    rows = conn.execute(
        "SELECT * FROM election_results ORDER BY tick DESC, vote_score DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _agent_locations() -> list[dict]:
    conn = _db()
    rows = conn.execute(
        "SELECT agent_id, agent_name, location FROM agent_locations"
    ).fetchall() if _table_exists(conn, "agent_locations") else []
    conn.close()
    return [dict(r) for r in rows]


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _recent_memories(n: int = 20) -> list[dict]:
    conn = _db()
    rows = conn.execute(
        "SELECT agent_name, tick, event, importance FROM agent_memory "
        "ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Gini (from CSV wealth, computed once at startup) ─────────────────────────

_GINI_CACHE: float | None = None

def _compute_gini() -> float:
    global _GINI_CACHE
    if _GINI_CACHE is not None:
        return _GINI_CACHE
    try:
        values = []
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    values.append(float(row["wealth"]))
                except (ValueError, KeyError):
                    pass
        if len(values) < 2:
            return 0.0
        values.sort()
        n, s = len(values), sum(values)
        if s == 0:
            return 0.0
        cum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(values))
        _GINI_CACHE = round(cum / (n * s), 4)
        return _GINI_CACHE
    except Exception:
        return 0.0


def _compute_metrics() -> dict:
    history = _world_history(20)
    state   = _world_state() or {}

    # Civic trust decay (slope over last ticks)
    trust_decay = 0.0
    if len(history) >= 2:
        trust_decay = round(
            (history[-1]["civic_trust"] - history[0]["civic_trust"])
            / max(1, len(history) - 1), 4
        )

    # Coalition tensions: blend of unrest + (100 - dynasty_score) * scrutiny
    tensions = 0.0
    if state:
        tensions = round(
            (state.get("unrest", 0) * 0.5
             + (100 - state.get("dynasty_score", 50)) * 0.003
             + state.get("scrutiny", 0) * 0.2) / 100, 4
        )

    return {
        "wealth_gini":          _compute_gini(),
        "civic_trust_decay":    trust_decay,
        "dynasty_office_rate":  round(state.get("dynasty_score", 0) / 100, 4),
        "coalition_tensions":   tensions,
        "current_tick":         state.get("tick", 0),
        "election_in":          state.get("election_in", "?"),
        "world_history":        history,
        "election_results":     _election_results()[-10:],
    }


# ── WebSocket manager ─────────────────────────────────────────────────────────

class _WSManager:
    def __init__(self):
        self._conns: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._conns.append(ws)

    def disconnect(self, ws: WebSocket):
        self._conns = [c for c in self._conns if c is not ws]

    async def broadcast(self, msg: dict):
        text = json.dumps(msg)
        dead = []
        for ws in self._conns:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._conns = [c for c in self._conns if c is not ws]

    @property
    def count(self) -> int:
        return len(self._conns)


manager = _WSManager()


# ── Background DB poller ─────────────────────────────────────────────────────

async def _poll_db():
    """Watch DB for new actions and tick advances; broadcast to all WS clients."""
    last_action_id = 0
    last_tick      = -1

    while True:
        try:
            # New agent actions
            new_actions = _actions_since(last_action_id)
            for action in new_actions:
                await manager.broadcast({"type": "agent_action", "data": action})
                last_action_id = max(last_action_id, action["id"]) 

            # Tick advance
            state = _world_state()
            if state and state["tick"] != last_tick:
                last_tick = state["tick"]
                await manager.broadcast({"type": "tick_complete", "data": state})

        except Exception:
            pass  # DB may not exist yet

        await asyncio.sleep(1.0)


# ── Lifespan ─────────────────────────────────────────────────────────────────

async def lifespan(app: FastAPI):
    _ensure_tables()
    _compute_gini()          # warm cache
    task = asyncio.create_task(_poll_db())
    yield
    task.cancel()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Dynasty Simulation API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── HTTP endpoints ────────────────────────────────────────────────────────────

@app.get("/state")
def get_state():
    s = _world_state()
    if s is None:
        return JSONResponse({"error": "simulation not started"}, status_code=503)
    return s


@app.get("/metrics")
def get_metrics():
    return _compute_metrics()


@app.get("/agents")
def get_agents():
    return _agent_locations()


@app.get("/actions")
def get_actions(limit: int = 40):
    return _recent_actions(limit)


@app.get("/memories")
def get_memories(limit: int = 20):
    return _recent_memories(limit)


@app.get("/elections")
def get_elections():
    return _election_results()


@app.get("/history")
def get_history(ticks: int = 30):
    return _world_history(ticks)


@app.get("/status")
def get_status():
    return {
        "ws_clients":   manager.count,
        "db":           Path(DB_PATH).exists(),
        "simulation":   _world_state() is not None,
        "server_time":  datetime.now(timezone.utc).isoformat(),
    }


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # Send current state immediately on connect
    state = _world_state()
    if state:
        await ws.send_text(json.dumps({"type": "world_state", "data": state}))
    metrics = _compute_metrics()
    await ws.send_text(json.dumps({"type": "metrics", "data": metrics}))
    try:
        while True:
            await ws.receive_text()   # keep-alive; client can ping
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── Static files (Phaser game) ────────────────────────────────────────────────

_static = Path("static")
if _static.exists():
    app.mount("/game", StaticFiles(directory="static", html=True), name="game")

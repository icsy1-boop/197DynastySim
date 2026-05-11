"""
db/logger.py
Writes simulation state to SQLite every tick.
Also writes JSON log files per simulated day for frontend replay.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SimLogger:
    """
    Two outputs:
    1. SQLite DB  — full relational store, queryable during/after sim
    2. JSON logs  — one file per simulated day, consumed by frontend
    """

    def __init__(self, run_id: str, output_dir: str = "output"):
        self.run_id = run_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.output_dir / f"{run_id}.db"
        self.log_dir = self.output_dir / run_id / "days"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._day_buffer: list = []               # events buffered for current day JSON
        self._day_buffer_conversations: list = [] # conversations buffered for day JSON
        self._current_day: int = 0

        self._init_db()

    # ── DB setup ─────────────────────────────────────────────────────────

    def _init_db(self):
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        c = self._conn.cursor()

        c.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS global_state (
            tick                INTEGER PRIMARY KEY,
            year                INTEGER,
            day                 INTEGER,
            hour                INTEGER,
            institution_strength REAL,
            corruption_index    REAL,
            welfare_index       REAL,
            audit_strength      REAL,
            media_presence      REAL,
            city_budget         REAL,
            citizen_trust       REAL,
            unrest_level        REAL,
            dynasty_score       REAL
        );

        CREATE TABLE IF NOT EXISTS agent_state (
            tick        INTEGER,
            agent_id    INTEGER,
            name        TEXT,
            role        TEXT,
            family_id   TEXT,
            location    TEXT,
            task        TEXT,
            satisfaction REAL,
            wealth      REAL,
            corrupt_acts INTEGER,
            honest_acts  INTEGER,
            PRIMARY KEY (tick, agent_id)
        );

        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tick        INTEGER,
            year        INTEGER,
            day         INTEGER,
            hour        INTEGER,
            agent_id    INTEGER,
            agent_name  TEXT,
            event_type  TEXT,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS relationships (
            tick        INTEGER,
            from_id     INTEGER,
            to_id       INTEGER,
            trust       REAL,
            PRIMARY KEY (tick, from_id, to_id)
        );

        CREATE TABLE IF NOT EXISTS corruption_acts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tick        INTEGER,
            agent_id    INTEGER,
            agent_name  TEXT,
            action_id   TEXT,
            declared_budget REAL,
            actual_budget   REAL,
            leakage         REAL,
            detected        INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tick        INTEGER,
            year        INTEGER,
            day         INTEGER,
            hour        INTEGER,
            agent_a_id  INTEGER,
            agent_a_name TEXT,
            agent_b_id  INTEGER,
            agent_b_name TEXT,
            dialogue    TEXT,
            outcome     TEXT,
            location    TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_events_tick   ON events(tick);
        CREATE INDEX IF NOT EXISTS idx_events_type   ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_agent_state_tick ON agent_state(tick);
        CREATE INDEX IF NOT EXISTS idx_conv_day      ON conversations(year, day);
        CREATE INDEX IF NOT EXISTS idx_conv_agents   ON conversations(agent_a_id, agent_b_id);
        """)
        self._conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    # ── Write methods ─────────────────────────────────────────────────────

    def log_global_state(self, clock, factors):
        c = self._conn.cursor()
        f = factors.to_dict()
        c.execute("""
            INSERT OR REPLACE INTO global_state VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            clock.tick, clock.year, clock.day, clock.hour,
            f["institution_strength"], f["corruption_index"],
            f["welfare_index"],        f["audit_strength"],
            f["media_presence"],       f["city_budget"],
            f["citizen_trust"],        f["unrest_level"],
            f["dynasty_score"],
        ))
        self._conn.commit()

    def log_agent_states(self, tick: int, agents: list):
        c = self._conn.cursor()
        rows = []
        for a in agents:
            rows.append((
                tick, a.unique_id, a.name, a.ROLE,
                getattr(a, "family_id", None),
                a.current_location, a.current_task,
                round(a.satisfaction, 1),
                round(a.personal_wealth, 2),
                a.corrupt_acts, a.honest_acts,
            ))
        c.executemany("""
            INSERT OR REPLACE INTO agent_state VALUES
            (?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        self._conn.commit()

    def log_event(self, tick: int, year: int, day: int, hour: int,
                  agent_id: int, agent_name: str,
                  event_type: str, description: str):
        c = self._conn.cursor()
        c.execute("""
            INSERT INTO events
            (tick,year,day,hour,agent_id,agent_name,event_type,description)
            VALUES (?,?,?,?,?,?,?,?)
        """, (tick, year, day, hour, agent_id, agent_name,
              event_type, description))
        self._conn.commit()

        # Buffer for JSON day log
        entry = {
            "tick": tick, "hour": hour,
            "agent_id": agent_id, "agent_name": agent_name,
            "type": event_type, "description": description,
        }
        self._day_buffer.append(entry)

    def log_corruption_act(self, tick: int, agent_id: int, agent_name: str,
                           action_id: str, declared: float, actual: float,
                           detected: bool = False):
        leakage = declared - actual if declared and actual else 0.0
        c = self._conn.cursor()
        c.execute("""
            INSERT INTO corruption_acts
            (tick,agent_id,agent_name,action_id,declared_budget,actual_budget,leakage,detected)
            VALUES (?,?,?,?,?,?,?,?)
        """, (tick, agent_id, agent_name, action_id,
              declared, actual, leakage, int(detected)))
        self._conn.commit()

    def log_conversation(self, tick: int, year: int, day: int, hour: int,
                         agent_a_id: int, agent_a_name: str,
                         agent_b_id: int, agent_b_name: str,
                         dialogue: str, outcome: str, location: str):
        c = self._conn.cursor()
        c.execute("""
            INSERT INTO conversations
            (tick,year,day,hour,agent_a_id,agent_a_name,agent_b_id,agent_b_name,dialogue,outcome,location)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (tick, year, day, hour, agent_a_id, agent_a_name,
              agent_b_id, agent_b_name, dialogue, outcome, location))
        self._conn.commit()
        self._day_buffer_conversations.append({
            "tick": tick, "hour": hour,
            "agent_a_id": agent_a_id, "agent_a_name": agent_a_name,
            "agent_b_id": agent_b_id, "agent_b_name": agent_b_name,
            "dialogue": dialogue, "outcome": outcome, "location": location,
        })

    def log_relationships(self, tick: int, graph):
        """Log a snapshot of the relationship graph — done daily, not every tick."""
        c = self._conn.cursor()
        rows = [
            (tick, u, v, round(d.get("trust", 0), 3))
            for u, v, d in graph.G.edges(data=True)
        ]
        c.executemany("""
            INSERT OR REPLACE INTO relationships VALUES (?,?,?,?)
        """, rows)
        self._conn.commit()

    # ── Day boundary ──────────────────────────────────────────────────────

    def flush_day(self, year: int, day: int, clock, factors, agents, graph):
        """
        Called at the end of each simulated day.
        Writes a self-contained JSON snapshot for that day.
        Frontend loads these for replay.
        """
        snapshot = {
            "run_id":        self.run_id,
            "year":          year,
            "day":           day,
            "global":        factors.to_dict(),
            "clock":         clock.to_dict(),
            "agents":        [a.to_dict() for a in agents],
            "events":        list(self._day_buffer),
            "conversations": list(self._day_buffer_conversations),
            "relationships": graph.summary(),
        }

        path = self.log_dir / f"y{year:02d}_d{day:03d}.json"
        with open(path, "w") as f:
            json.dump(snapshot, f, separators=(",", ":"))

        self._day_buffer = []
        self._day_buffer_conversations = []
        logger.debug(f"Flushed day snapshot → {path.name}")

    # ── Checkpoint ────────────────────────────────────────────────────────

    def checkpoint(self, clock, factors, agents):
        """
        Write a lightweight checkpoint every 10 sim-days.
        Used for resume on crash.
        """
        path = self.output_dir / f"{self.run_id}_checkpoint.json"
        data = {
            "clock":   clock.to_dict(),
            "factors": factors.to_dict(),
            "saved_at": datetime.utcnow().isoformat(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Checkpoint saved at tick {clock.tick}")

    # ── Read helpers (for FastAPI) ─────────────────────────────────────────

    def get_global_history(self) -> list:
        c = self._conn.cursor()
        c.execute("SELECT * FROM global_state ORDER BY tick")
        return [dict(row) for row in c.fetchall()]

    def get_recent_events(self, limit: int = 50) -> list:
        c = self._conn.cursor()
        c.execute("""
            SELECT * FROM events
            ORDER BY tick DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in c.fetchall()]

    def get_corruption_summary(self) -> dict:
        c = self._conn.cursor()
        c.execute("""
            SELECT
                COUNT(*)            AS total_acts,
                SUM(leakage)        AS total_leakage,
                SUM(detected)       AS detected_acts,
                AVG(leakage)        AS avg_leakage
            FROM corruption_acts
        """)
        row = c.fetchone()
        return dict(row) if row else {}

    def get_agent_corruption_rank(self) -> list:
        c = self._conn.cursor()
        c.execute("""
            SELECT agent_name, COUNT(*) as acts, SUM(leakage) as leakage
            FROM corruption_acts
            GROUP BY agent_id
            ORDER BY leakage DESC
        """)
        return [dict(row) for row in c.fetchall()]

    def close(self):
        if self._conn:
            self._conn.close()

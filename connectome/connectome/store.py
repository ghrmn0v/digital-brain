import json
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    behavior_id TEXT,
    event TEXT,
    source TEXT,
    priority REAL,
    state TEXT,
    priority_level TEXT,
    confidence REAL,
    activity_json TEXT,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    behavior_id TEXT,
    feedback TEXT,
    reward_value REAL,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS model_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    weights_json TEXT,
    updated_at REAL
);
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions (created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback (created_at);
"""


class SqliteStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or ":memory:"
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    def record_decision(self, decision: Dict[str, Any], behavior_id: str) -> None:
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO decisions
                    (behavior_id, event, source, priority, state, priority_level, confidence, activity_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    behavior_id,
                    decision.get("event"),
                    decision.get("source"),
                    decision.get("priority"),
                    decision.get("fetch"),
                    decision.get("priority_level"),
                    decision.get("confidence"),
                    json.dumps(decision.get("activity", {})),
                    time.time(),
                ),
            )
            self.conn.commit()

    def record_feedback(self, feedback_type: str, reward_value: float, behavior_id: str) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO feedback (behavior_id, feedback, reward_value, created_at) VALUES (?, ?, ?, ?)",
                (behavior_id, feedback_type, reward_value, time.time()),
            )
            self.conn.commit()

    def save_weights(self, weights: Dict[tuple, float]) -> None:
        serializable = {f"{k[0]}->{k[1]}": v for k, v in weights.items()}
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO model_state (id, weights_json, updated_at) VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET weights_json = excluded.weights_json, updated_at = excluded.updated_at
                """,
                (json.dumps(serializable), time.time()),
            )
            self.conn.commit()

    def load_weights(self) -> Dict[tuple, float]:
        with self.lock:
            row = self.conn.execute(
                "SELECT weights_json FROM model_state WHERE id = 1"
            ).fetchone()
        if not row:
            return {}
        raw = json.loads(row[0])
        return {tuple(key.split("->")): float(value) for key, value in raw.items()}

    def decisions(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                f"""
                SELECT behavior_id, event, source, priority, state, priority_level, confidence, created_at
                FROM decisions ORDER BY id DESC LIMIT {int(limit)}
                """
            ).fetchall()
        columns = ["behavior_id", "event", "source", "priority", "state", "priority_level", "confidence", "created_at"]
        return [dict(zip(columns, row)) for row in rows]

    def feedback_rows(self) -> List[Dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT behavior_id, feedback, reward_value, created_at FROM feedback ORDER BY id"
            ).fetchall()
        columns = ["behavior_id", "feedback", "reward_value", "created_at"]
        return [dict(zip(columns, row)) for row in rows]

    def counts(self) -> Dict[str, int]:
        with self.lock:
            decisions = self.conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            feedback = self.conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        return {"decisions": decisions, "feedback": feedback}

    def latest_weights_json(self) -> Optional[str]:
        with self.lock:
            row = self.conn.execute(
                "SELECT weights_json FROM model_state WHERE id = 1"
            ).fetchone()
        return row[0] if row else None
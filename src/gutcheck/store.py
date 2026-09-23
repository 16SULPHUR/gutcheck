import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    trace_id       TEXT PRIMARY KEY,
    created_at     TEXT NOT NULL,
    endpoint       TEXT NOT NULL,
    model          TEXT,
    routing_reason TEXT,
    latency_ms     REAL NOT NULL,
    state          TEXT
);
CREATE TABLE IF NOT EXISTS answers (
    trace_id           TEXT NOT NULL REFERENCES decisions (trace_id),
    question_id        TEXT NOT NULL,
    type               TEXT NOT NULL,
    question           TEXT NOT NULL,
    answer             TEXT NOT NULL,
    answer_probability REAL NOT NULL,
    verdict            TEXT,
    PRIMARY KEY (trace_id, question_id)
);
"""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


@dataclass
class AnswerRecord:
    question_id: str
    question: dict[str, Any]
    answer: dict[str, Any]
    answer_probability: float
    verdict: str | None = None


@dataclass
class DecisionRecord:
    trace_id: str
    endpoint: str
    model: str | None
    routing_reason: str | None
    latency_ms: float
    state: Any
    answers: list[AnswerRecord] = field(default_factory=list)


class DecisionStore:
    """Append-only SQLite log of decisions, safe to call from worker threads."""

    def __init__(self, path: str, save_state: bool = True):
        self._save_state = save_state
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        if path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    def record(self, rec: DecisionRecord) -> None:
        now = datetime.now(timezone.utc).isoformat()
        state = _json(rec.state) if self._save_state else None
        rows = [
            (
                rec.trace_id,
                a.question_id,
                a.answer["type"],
                _json(a.question),
                _json(a.answer[a.answer["type"]]),
                a.answer_probability,
                a.verdict,
            )
            for a in rec.answers
        ]
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.trace_id,
                    now,
                    rec.endpoint,
                    rec.model,
                    rec.routing_reason,
                    rec.latency_ms,
                    state,
                ),
            )
            self._conn.executemany("INSERT INTO answers VALUES (?, ?, ?, ?, ?, ?, ?)", rows)

    def execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

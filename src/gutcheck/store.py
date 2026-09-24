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
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id    TEXT NOT NULL,
    question_id TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    label       INTEGER,
    correct     INTEGER NOT NULL,
    source      TEXT,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS feedback_answer ON feedback (trace_id, question_id);
CREATE TABLE IF NOT EXISTS temperatures (
    calibration_key TEXT PRIMARY KEY,
    temperature     REAL NOT NULL,
    n               INTEGER NOT NULL,
    fitted_at       TEXT NOT NULL
);
"""

# columns added after the first release; created on older databases at startup
_ANSWER_COLUMNS = {
    # fingerprint of the question definition; feedback is pooled per key for recalibration
    "calibration_key": "TEXT",
    # the option order of `raw`, e.g. ["false", "true"]
    "options": "TEXT",
    # the model's probabilities before any temperature was applied
    "raw": "TEXT",
    "temperature": "REAL",
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


@dataclass
class AnswerRecord:
    question_id: str
    question: dict[str, Any]
    answer: dict[str, Any]
    answer_probability: float
    verdict: str | None = None
    calibration_key: str | None = None
    options: list[str] | None = None
    raw: list[float] | None = None
    temperature: float = 1.0


@dataclass
class FeedbackRecord:
    trace_id: str
    question_id: str
    label: int | None
    correct: bool
    source: str | None = None
    note: str | None = None


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
        have = {row[1] for row in self._conn.execute("PRAGMA table_info(answers)")}
        with self._conn:
            for name, kind in _ANSWER_COLUMNS.items():
                if name not in have:
                    self._conn.execute(f"ALTER TABLE answers ADD COLUMN {name} {kind}")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS answers_key ON answers (calibration_key)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS decisions_created ON decisions (created_at)"
            )

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
                a.calibration_key,
                _json(a.options) if a.options is not None else None,
                _json(a.raw) if a.raw is not None else None,
                a.temperature,
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
            self._conn.executemany(
                "INSERT INTO answers (trace_id, question_id, type, question, answer,"
                " answer_probability, verdict, calibration_key, options, raw, temperature)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

    def answer(self, trace_id: str, question_id: str) -> dict[str, Any] | None:
        rows = self.execute(
            "SELECT type, options, raw, calibration_key FROM answers"
            " WHERE trace_id = ? AND question_id = ?",
            (trace_id, question_id),
        )
        if not rows:
            return None
        kind, options, raw, key = rows[0]
        return {
            "type": kind,
            "options": json.loads(options) if options else None,
            "raw": json.loads(raw) if raw else None,
            "calibration_key": key,
        }

    def has_decision(self, trace_id: str) -> bool:
        return bool(self.execute("SELECT 1 FROM decisions WHERE trace_id = ?", (trace_id,)))

    def add_feedback(self, records: list[FeedbackRecord]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (r.trace_id, r.question_id, now, r.label, int(r.correct), r.source, r.note)
            for r in records
        ]
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT INTO feedback (trace_id, question_id, created_at, label, correct,"
                " source, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

    def labelled(self) -> list[tuple[str, list[float], int]]:
        """(calibration_key, raw probabilities, true label) for answers with feedback.

        When an answer was corrected more than once, the latest label wins.
        """
        rows = self.execute(
            "SELECT a.calibration_key, a.raw, f.label FROM answers a"
            " JOIN feedback f ON f.id = (SELECT MAX(id) FROM feedback"
            "   WHERE trace_id = a.trace_id AND question_id = a.question_id)"
            " WHERE a.calibration_key IS NOT NULL AND a.raw IS NOT NULL"
            " AND f.label IS NOT NULL"
        )
        return [(key, json.loads(raw), label) for key, raw, label in rows]

    def questions(self) -> dict[str, dict[str, Any]]:
        """Latest question id and definition seen for each calibration key."""
        rows = self.execute(
            "SELECT calibration_key, question_id, question FROM answers WHERE rowid IN"
            " (SELECT MAX(rowid) FROM answers WHERE calibration_key IS NOT NULL"
            "  GROUP BY calibration_key)"
        )
        return {key: {"question_id": qid, **json.loads(q)} for key, qid, q in rows}

    def stats(self, since: str) -> dict[str, Any]:
        """Aggregates over decisions created at or after `since` (an ISO timestamp)."""
        per_hour = self.execute(
            "SELECT substr(created_at, 1, 13), COUNT(*) FROM decisions"
            " WHERE created_at >= ? GROUP BY 1 ORDER BY 1",
            (since,),
        )
        latencies = [
            r[0]
            for r in self.execute(
                "SELECT latency_ms FROM decisions WHERE created_at >= ? ORDER BY latency_ms",
                (since,),
            )
        ]
        per_question = self.execute(
            "SELECT a.calibration_key, a.verdict, COUNT(*) FROM answers a"
            " JOIN decisions d USING (trace_id)"
            " WHERE d.created_at >= ? AND a.calibration_key IS NOT NULL GROUP BY 1, 2",
            (since,),
        )
        labelled = self.execute(
            "SELECT a.calibration_key, COUNT(*), SUM(f.correct) FROM answers a"
            " JOIN decisions d USING (trace_id)"
            " JOIN feedback f ON f.id = (SELECT MAX(id) FROM feedback"
            "   WHERE trace_id = a.trace_id AND question_id = a.question_id)"
            " WHERE d.created_at >= ? GROUP BY 1",
            (since,),
        )
        return {
            "per_hour": per_hour,
            "latencies": latencies,
            "per_question": per_question,
            "labelled": labelled,
        }

    def temperatures(self) -> dict[str, float]:
        return dict(self.execute("SELECT calibration_key, temperature FROM temperatures"))

    def save_temperatures(self, fitted: dict[str, tuple[float, int]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO temperatures VALUES (?, ?, ?, ?)",
                [(key, t, n, now) for key, (t, n) in fitted.items()],
            )

    def execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

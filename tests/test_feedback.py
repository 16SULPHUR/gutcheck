import sqlite3

import pytest

from gutcheck.feedback import fingerprint, options, recalibrate, resolve
from gutcheck.store import AnswerRecord, DecisionRecord, DecisionStore, FeedbackRecord


def test_fingerprint_ignores_policy_and_order():
    a = {"type": "noul", "instructions": "Urgent?", "policy": {"act_at": 0.8}}
    b = {"instructions": "Urgent?", "type": "noul"}
    assert fingerprint(a) == fingerprint(b)
    assert fingerprint(a) != fingerprint({**b, "instructions": "Urgent now?"})
    assert fingerprint(a, "prompt-guard@2") != fingerprint(a)
    assert fingerprint(a, "prompt-guard@2") == fingerprint(b, "prompt-guard@2")


def test_options():
    assert options({"type": "noul", "noul": 0.2}) == ["false", "true"]
    assert options({"type": "score", "probabilities": {"0": 0.5, "1": 0.5}}) == ["0", "1"]


@pytest.mark.parametrize(
    ("opts", "raw", "answer", "correct", "expected"),
    [
        (["false", "true"], [0.2, 0.8], True, None, (1, True)),
        (["false", "true"], [0.2, 0.8], "false", None, (0, False)),
        (["false", "true"], [0.2, 0.8], None, False, (0, False)),
        (["a", "b", "c"], [0.1, 0.7, 0.2], "c", None, (2, False)),
        (["a", "b", "c"], [0.1, 0.7, 0.2], None, True, (1, True)),
        (["a", "b", "c"], [0.1, 0.7, 0.2], None, False, (None, False)),
        (["0", "1", "2"], [0.1, 0.2, 0.7], 2, None, (2, True)),
    ],
)
def test_resolve(opts, raw, answer, correct, expected):
    assert resolve(opts, raw, answer, correct) == expected


def test_resolve_rejects_unknown_option():
    with pytest.raises(ValueError, match="not one of the options"):
        resolve(["a", "b"], [0.5, 0.5], "z")


def _log(store, i, raw, key="k1"):
    store.record(
        DecisionRecord(
            trace_id=f"t{i}",
            endpoint="decide",
            model="english",
            routing_reason=None,
            latency_ms=1.0,
            state="s",
            answers=[
                AnswerRecord(
                    question_id="q",
                    question={"type": "noul", "instructions": "?"},
                    answer={"type": "noul", "noul": raw[1]},
                    answer_probability=max(raw),
                    calibration_key=key,
                    options=["false", "true"],
                    raw=raw,
                )
            ],
        )
    )


def test_recalibrate_fits_overconfident_question(tmp_path):
    store = DecisionStore(str(tmp_path / "g.db"))
    for i in range(40):
        _log(store, i, [0.05, 0.95])
        # right 70% of the time, and the first label is superseded by a later correction
        store.add_feedback([FeedbackRecord(f"t{i}", "q", 0, False)])
        store.add_feedback([FeedbackRecord(f"t{i}", "q", 1 if i % 10 < 7 else 0, i % 10 < 7)])
    _log(store, 99, [0.5, 0.5], key="rare")
    store.add_feedback([FeedbackRecord("t99", "q", 1, True)])

    refits = recalibrate(store, min_samples=30)
    assert refits["k1"].n == 40
    assert refits["k1"].accuracy == 0.7
    assert refits["k1"].temperature > 1.5
    assert refits["k1"].ece_after < refits["k1"].ece_before
    assert refits["rare"].temperature is None
    assert store.temperatures() == {"k1": refits["k1"].temperature}


def test_old_database_gets_new_columns(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.executescript(
        "CREATE TABLE answers (trace_id TEXT, question_id TEXT, type TEXT, question TEXT,"
        " answer TEXT, answer_probability REAL, verdict TEXT);"
    )
    db.close()
    DecisionStore(str(path)).close()
    cols = {r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(answers)")}
    assert {"calibration_key", "options", "raw", "temperature"} <= cols

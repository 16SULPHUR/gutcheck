import pytest
from fastapi.testclient import TestClient
from laya.router import Router

from gutcheck.app import create_app
from gutcheck.config import load_settings
from gutcheck.engine import LayaEngine

URGENT = {"urgent": {"type": "noul", "instructions": "Is this urgent?"}}
DEPT = {
    "department": {
        "type": "choice",
        "instructions": "Which department?",
        "criteria": {"billing": "money", "technical": "bugs"},
    }
}


def decide(client, questions=URGENT, **extra):
    r = client.post("/v1/decide", json={"state": "hello", "questions": questions, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_feedback_is_recorded(client, agents):
    trace = decide(client, {**URGENT, **DEPT})["trace_id"]
    r = client.post(
        "/v1/feedback",
        json={
            "trace_id": trace,
            "answers": {"urgent": {"answer": False}, "department": {"correct": True}},
            "source": "agent-review",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["recorded"] == [
        {"question_id": "urgent", "answer": "false", "correct": False},
        {"question_id": "department", "answer": "billing", "correct": True},
    ]


@pytest.mark.parametrize(
    ("body", "status", "detail"),
    [
        ({"trace_id": "gc_nope", "answers": {"urgent": {"correct": True}}}, 404, "no decision"),
        ({"answers": {"missing": {"correct": True}}}, 404, "no question"),
        ({"answers": {"urgent": {"answer": "maybe"}}}, 422, "not one of the options"),
        ({"answers": {"urgent": {"answer": True, "correct": True}}}, 422, "exactly one"),
        ({"answers": {}}, 422, ""),
    ],
)
def test_feedback_errors(client, body, status, detail):
    body.setdefault("trace_id", decide(client)["trace_id"])
    r = client.post("/v1/feedback", json=body)
    assert r.status_code == status
    assert detail in r.text


def test_feedback_needs_the_decision_log(make_client):
    with make_client(store={"path": None}) as c:
        r = c.post("/v1/feedback", json={"trace_id": "x", "answers": {"u": {"correct": True}}})
        assert r.status_code == 409
        assert c.post("/v1/calibrate").status_code == 409


def test_calibration_from_feedback_changes_verdicts(make_client, agents, tmp_path):
    with make_client(calibration={"min_samples": 10}) as c:
        # the fake always answers yes at 0.95; the truth is yes only 60% of the time
        for i in range(20):
            trace = decide(c)["trace_id"]
            c.post(
                "/v1/feedback",
                json={"trace_id": trace, "answers": {"urgent": {"correct": i % 5 < 3}}},
            )
        assert decide(c)["answers"]["urgent"]["verdict"] == "act"

        r = c.post("/v1/calibrate")
        assert r.status_code == 200, r.text
        (q,) = r.json()["questions"]
        assert q["question_id"] == "urgent"
        assert q["n"] == 20
        assert q["accuracy"] == 0.6
        assert q["temperature"] > 1

        answer = decide(c)["answers"]["urgent"]
        assert answer["noul"] < 0.8
        assert answer["verdict"] != "act"
        # a per-question policy does not change the question's identity
        policy = {"urgent": {**URGENT["urgent"], "policy": {"act_at": 0.99, "review_at": 0.5}}}
        assert decide(c, policy)["answers"]["urgent"]["noul"] == answer["noul"]

    # learned temperatures survive a restart
    router = Router()
    for name, agent in agents.items():
        router.attach(name, agent)
    settings = load_settings(store={"path": str(tmp_path / "gutcheck.db")})
    app = create_app(settings, engine=LayaEngine(settings.engine, router=router))
    with TestClient(app) as c:
        assert decide(c)["answers"]["urgent"]["noul"] == answer["noul"]


def test_calibrate_reports_questions_short_of_labels(client):
    trace = decide(client)["trace_id"]
    client.post("/v1/feedback", json={"trace_id": trace, "answers": {"urgent": {"correct": True}}})
    r = client.post("/v1/calibrate", json={"min_samples": 5})
    assert r.json()["questions"][0]["temperature"] is None


def test_stats(client):
    trace = decide(client, packs=["prompt-guard"])["trace_id"]
    decide(client)
    client.post("/v1/feedback", json={"trace_id": trace, "answers": {"urgent": {"correct": False}}})
    s = client.get("/v1/stats", params={"hours": 24}).json()
    assert s["decisions"] == 2
    assert sum(h["decisions"] for h in s["per_hour"]) == 2
    assert s["latency_ms"]["p50"] is not None
    assert sum(s["verdicts"].values()) == 4
    urgent = next(q for q in s["questions"] if q["question_id"] == "urgent")
    assert (urgent["answers"], urgent["feedback"], urgent["accuracy"]) == (2, 1, 0.0)
    assert {q["question_id"] for q in s["questions"]} == {
        "urgent",
        "prompt-guard.injection",
        "prompt-guard.jailbreak",
    }


def test_metrics(client):
    trace = decide(client, packs=["prompt-guard"])["trace_id"]
    client.post("/v1/feedback", json={"trace_id": trace, "answers": {"urgent": {"correct": True}}})
    text = client.get("/metrics").text
    assert 'gutcheck_decisions_total{endpoint="decide",model="english"} 1.0' in text
    assert 'gutcheck_verdicts_total{question="inline",verdict="act"} 1.0' in text
    assert 'question="prompt-guard.injection"' in text
    assert 'gutcheck_feedback_total{correct="true",question="inline"} 1.0' in text
    assert "gutcheck_inference_seconds_bucket" in text


def test_dashboard_and_auth(make_client):
    with make_client(api_key="s3cret") as c:
        page = c.get("/dashboard")
        assert page.status_code == 200
        assert "/v1/stats" in page.text
        assert c.get("/v1/stats").status_code == 401
        assert c.get("/metrics").status_code == 401
        auth = {"Authorization": "Bearer s3cret"}
        assert c.get("/v1/stats", headers=auth).status_code == 200
        assert c.get("/metrics", headers=auth).status_code == 200

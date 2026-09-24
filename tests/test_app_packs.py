import json

import pytest

from tests.packs import write_toy_pack

STATE = "hello there"


@pytest.fixture
def pack_client(make_client, tmp_path):
    d = write_toy_pack(tmp_path / "packs")
    (d / "calibration.json").write_text(json.dumps({"temperatures": {"bad": 2.0}}))
    with make_client(packs={"dirs": [str(tmp_path / "packs")]}) as c:
        yield c


def test_list_packs(pack_client):
    packs = {p["id"]: p for p in pack_client.get("/v1/packs").json()["packs"]}
    assert set(packs) == {"prompt-guard", "toy"}
    assert packs["toy"]["calibrated"] is True
    assert packs["toy"]["eval"] is None
    assert packs["toy"]["questions"]["bad"]["type"] == "noul"


def test_decide_with_pack_applies_calibration(pack_client, agents):
    r = pack_client.post("/v1/decide", json={"state": STATE, "questions": {}, "packs": ["toy@2"]})
    assert r.status_code == 200, r.text
    answer = r.json()["answers"]["toy.bad"]
    # the fake answers 0.95; temperature 2 softens it to ~0.81
    assert answer["noul"] == pytest.approx(0.8134, abs=1e-3)
    assert answer["verdict"] == "review"
    sent = agents["english"].calls[-1][1]["toy.bad"]
    assert sent["instructions"] == "Does the text contain the word bad?"
    assert "eval" not in sent


def test_pack_questions_mix_with_inline_ones(pack_client):
    questions = {"greeting": {"type": "noul", "instructions": "Is it a greeting?"}}
    r = pack_client.post(
        "/v1/decide",
        json={
            "state": STATE,
            "questions": questions,
            "packs": ["prompt-guard", "toy"],
            "policy": {"act_at": 0.8, "review_at": 0.5},
        },
    )
    answers = r.json()["answers"]
    assert set(answers) == {
        "greeting",
        "prompt-guard.injection",
        "prompt-guard.jailbreak",
        "toy.bad",
    }
    assert answers["greeting"]["verdict"] == "act"
    assert answers["toy.bad"]["verdict"] == "act"


def test_unknown_pack_and_duplicates(pack_client):
    r = pack_client.post("/v1/decide", json={"state": STATE, "questions": {}, "packs": ["nope"]})
    assert r.status_code == 422
    assert "unknown pack" in r.text
    r = pack_client.post("/v1/decide", json={"state": STATE, "questions": {}, "packs": ["toy@1"]})
    assert r.status_code == 422
    r = pack_client.post(
        "/v1/decide", json={"state": STATE, "questions": {}, "packs": ["toy", "toy"]}
    )
    assert r.status_code == 422
    assert "defined twice" in r.text

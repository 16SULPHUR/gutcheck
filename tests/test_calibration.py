import pytest

from gutcheck.calibration import apply_temperature, fit_temperature, scale


def test_scale_identity_and_sharpening():
    assert scale([0.2, 0.8], 1.0) == pytest.approx([0.2, 0.8])
    assert scale([0.2, 0.8], 0.5)[1] > 0.8
    assert scale([0.2, 0.8], 2.0)[1] < 0.8


def test_fit_temperature_softens_overconfident_predictions():
    # 95% confident but right only 70% of the time
    samples = [([0.05, 0.95], 1)] * 70 + [([0.05, 0.95], 0)] * 30
    t = fit_temperature(samples)
    assert t > 1.5
    assert scale([0.05, 0.95], t)[1] == pytest.approx(0.7, abs=0.05)


def test_fit_temperature_without_samples():
    assert fit_temperature([]) == 1.0


def test_apply_temperature_noul():
    out = apply_temperature({"type": "noul", "noul": 0.9, "confidence": 0.9}, 3.0)
    assert 0.5 < out["noul"] < 0.9
    assert out["confidence"] == out["noul"]


def test_apply_temperature_choice_and_score():
    choice = {
        "type": "choice",
        "choice": "a",
        "probabilities": {"a": 0.7, "b": 0.2, "c": 0.1},
        "confidence": 0.3,
    }
    out = apply_temperature(choice, 0.5)
    assert out["choice"] == "a"
    assert out["probabilities"]["a"] > 0.7
    assert out["confidence"] > 0.3

    score = {"type": "score", "score": 1.8, "probabilities": {"0": 0.1, "1": 0.0, "2": 0.9}}
    out = apply_temperature(score, 0.5)
    assert out["score"] > 1.8


def test_apply_temperature_one_is_a_noop():
    answer = {"type": "noul", "noul": 0.9}
    assert apply_temperature(answer, 1.0) is answer

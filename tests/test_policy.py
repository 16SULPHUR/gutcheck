import pytest
from pydantic import ValidationError

from gutcheck.config import Thresholds
from gutcheck.policy import answer_probability, verdict


def test_answer_probability():
    assert answer_probability({"type": "noul", "noul": 0.2}) == pytest.approx(0.8)
    assert answer_probability({"type": "noul", "noul": 0.9}) == pytest.approx(0.9)
    choice = {"type": "choice", "choice": "a", "probabilities": {"a": 0.7, "b": 0.3}}
    assert answer_probability(choice) == 0.7
    score = {"type": "score", "score": 1.1, "probabilities": {"0": 0.1, "1": 0.7, "2": 0.2}}
    assert answer_probability(score) == 0.7


@pytest.mark.parametrize(
    ("p", "expected"),
    [(0.95, "act"), (0.9, "act"), (0.89, "review"), (0.6, "review"), (0.59, "escalate")],
)
def test_default_bands(p, expected):
    assert verdict(p, Thresholds()) == expected


def test_thresholds_must_be_ordered():
    with pytest.raises(ValidationError):
        Thresholds(act_at=0.5, review_at=0.7)
    assert Thresholds(act_at=0.7, review_at=0.7).review_at == 0.7

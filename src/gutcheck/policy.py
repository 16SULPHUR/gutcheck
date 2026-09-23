from typing import Any, Literal

from gutcheck.config import Thresholds

Verdict = Literal["act", "review", "escalate"]


def answer_probability(answer: dict[str, Any]) -> float:
    """Probability the model assigns to the answer it returned."""
    if answer["type"] == "noul":
        p = float(answer["noul"])
        return max(p, 1.0 - p)
    return max(float(v) for v in answer["probabilities"].values())


def verdict(probability: float, thresholds: Thresholds) -> Verdict:
    if probability >= thresholds.act_at:
        return "act"
    if probability >= thresholds.review_at:
        return "review"
    return "escalate"

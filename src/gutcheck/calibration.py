import math
from collections.abc import Sequence
from typing import Any

_EPS = 1e-6
# log-spaced 0.2 .. 5.0
_GRID = [math.exp(math.log(0.2) + i * (math.log(5.0) - math.log(0.2)) / 60) for i in range(61)]


def distribution(answer: dict[str, Any]) -> list[float]:
    """The answer's probabilities as a vector (noul: [P(false), P(true)])."""
    if answer["type"] == "noul":
        p = float(answer["noul"])
        return [1.0 - p, p]
    return [float(v) for v in answer["probabilities"].values()]


def scale(probs: Sequence[float], temperature: float) -> list[float]:
    logs = [math.log(min(max(p, _EPS), 1.0)) / temperature for p in probs]
    top = max(logs)
    exps = [math.exp(v - top) for v in logs]
    total = sum(exps)
    return [e / total for e in exps]


def _confidence(probs: list[float]) -> float:
    # Laya's definition: 1 - normalised entropy
    k = len(probs)
    if k < 2:
        return 1.0
    ent = -sum(p * math.log(max(p, 1e-12)) for p in probs)
    return max(0.0, min(1.0, 1.0 - ent / math.log(k)))


def apply_temperature(answer: dict[str, Any], temperature: float) -> dict[str, Any]:
    """Return a copy of a Laya answer with its probabilities rescaled by `temperature`."""
    if temperature == 1.0:
        return answer
    probs = scale(distribution(answer), temperature)
    out = dict(answer)
    if answer["type"] == "noul":
        out["noul"] = round(probs[1], 4)
        out["confidence"] = round(max(probs), 4)
        return out
    keys = list(answer["probabilities"])
    out["probabilities"] = {k: round(p, 4) for k, p in zip(keys, probs, strict=True)}
    out["confidence"] = round(_confidence(probs), 4)
    if answer["type"] == "choice":
        out["choice"] = keys[max(range(len(probs)), key=probs.__getitem__)]
    else:
        out["score"] = round(sum(int(k) * p for k, p in zip(keys, probs, strict=True)), 4)
    return out


def nll(samples: Sequence[tuple[Sequence[float], int]], temperature: float) -> float:
    return -sum(
        math.log(max(scale(probs, temperature)[label], _EPS)) for probs, label in samples
    ) / len(samples)


def fit_temperature(samples: Sequence[tuple[Sequence[float], int]]) -> float:
    """Temperature minimising negative log-likelihood of the true labels (grid search)."""
    if not samples:
        return 1.0
    return min(_GRID, key=lambda t: nll(samples, t))

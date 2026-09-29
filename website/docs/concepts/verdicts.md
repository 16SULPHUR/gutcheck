# Verdicts and policies

A probability alone does not tell your code what to do. A verdict does.

## The rule

The **answer probability** is the probability of the answer returned: the top option for `choice` and `score`, and `max(p, 1 - p)` for `noul`, so a confident "no" counts as confident.

| Condition | Verdict |
| --- | --- |
| answer probability at or above `act_at` | `act` |
| at or above `review_at` | `review` |
| below `review_at` | `escalate` |

Defaults are `act_at: 0.9` and `review_at: 0.6`.

## Where thresholds come from

The most specific one wins:

1. Per question: a `policy` object on the question.
2. Per request: a `policy` object on the request.
3. Config: `policy.act_at` and `policy.review_at`.

```json
{
  "policy": {"act_at": 0.85, "review_at": 0.6},
  "questions": {
    "refund": {"type": "noul", "instructions": "...", "policy": {"act_at": 0.95, "review_at": 0.7}}
  }
}
```

Set stricter thresholds where a wrong automatic action is expensive (refunds, deletions), looser where it is cheap (tagging).

## Choosing thresholds

Thresholds only mean something on calibrated probabilities. Uncalibrated, "0.9" may be right 60% of the time. See [Calibration](/docs/concepts/calibration), then pick `act_at` from your own eval: the accuracy of answers marked `act` is reported for every pack in its `EVAL.md`.

The [playground](/demos/#decision-playground) lets you move thresholds and watch verdicts change.

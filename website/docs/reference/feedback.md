# Feedback and calibrate

## POST /v1/feedback

Tell gutcheck what the right answer was. Give the true answer, or just whether the returned one was right.

```bash
curl -s localhost:8080/v1/feedback -H 'Content-Type: application/json' -d '{
  "trace_id": "gc_4f9c...",
  "answers": {"refund": {"answer": false}, "department": {"correct": true}},
  "source": "support-agent"
}'
```

| Field | Type | Notes |
| --- | --- | --- |
| `trace_id` | string | From the decide response |
| `answers` | object | Question name to `{answer}` or `{correct}`. Exactly one per item |
| `source` | string | Optional, who labelled it |
| `note` | string | Optional |

`answer` is `true` or `false` for `noul`, an option for `choice`, and a level for `score`. A `correct: false` on a yes/no question implies the other answer. On questions with more options it counts toward accuracy but not calibration. A later label for the same answer replaces an earlier one.

## POST /v1/calibrate

Refits a temperature for every question with at least `calibration.min_samples` labels (default 30) and applies it to new decisions immediately.

```bash
curl -s -X POST localhost:8080/v1/calibrate -H 'Content-Type: application/json' -d '{"min_samples": 50}'
```

The body is optional. The response reports, per question, the label count `n`, the fitted `temperature`, `accuracy`, and ECE before and after. Learned temperatures are saved in the decision log, survive restarts and override a pack's shipped calibration. Questions are matched by their wording and options, so editing a question starts it fresh.

`gutcheck calibrate` does the same offline. A running server picks its results up on restart.

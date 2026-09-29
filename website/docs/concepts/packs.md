# Question packs

A pack is a versioned set of questions with the datasets that test them, a fitted calibration and a generated eval report. Packs make a question set something you can trust, review in a pull request and regress-test in CI.

## What is in a pack

| File | Written by | Holds |
| --- | --- | --- |
| `pack.yaml` | you | id, version, questions, eval datasets, optional `model:` checkpoint |
| `calibration.json` | `gutcheck eval --write` | one fitted temperature per question |
| `eval.json` | `gutcheck eval --write` | the metrics CI compares against |
| `EVAL.md` | `gutcheck eval --write` | the human-readable report |

## Honest evals

Each question names two splits of a dataset. The **calibration** split fits the temperature (and is the training data when you fine-tune). The **test** split is only used to report results. Datasets are pinned to an exact revision, and can be local CSV, JSONL or Parquet, or on the Hugging Face Hub.

## Regression gate

`gutcheck eval --check` re-runs every pack and exits 1 if calibrated accuracy drops by more than 0.02 or ECE rises by more than 0.03 against the committed `eval.json`. CI runs it on every pull request for the bundled packs.

## Using a pack

```json
{"state": "...", "questions": {}, "packs": ["prompt-guard@2"]}
```

Answers come back as `<pack>.<question>`, already calibrated. `GET /v1/packs` lists what is installed.

## Bundled

| Pack | Questions | Details |
| --- | --- | --- |
| `prompt-guard` | `injection`, `jailbreak` | [prompt-guard](/docs/packs/prompt-guard) |

To make your own, see [Write a question pack](/docs/guides/writing-a-pack).

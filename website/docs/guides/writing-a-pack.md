# Write a question pack

A pack is a directory with a `pack.yaml`. Put it under a directory listed in `packs.dirs`.

## 1. Define the questions

```yaml
id: support-triage
version: 1
description: Routes support tickets.
questions:
  urgent:
    type: noul
    instructions: Does the customer need help within the hour?
    policy: {act_at: 0.95, review_at: 0.7}   # optional, per question
    eval:
      test: {path: test.jsonl, license: CC-BY-4.0}          # or repo/revision on Hugging Face
      calibration: {path: train.jsonl, license: CC-BY-4.0}  # a separate split
      text_field: text
      label_field: label
      labels: {"urgent": true, "normal": false}  # quote keys: YAML reads yes/no as booleans
```

Datasets can be CSV, JSONL or Parquet (`pip install "gutcheck[eval]"` for Parquet and Hub downloads), local or on the Hugging Face Hub pinned to a revision. Keep the calibration and test splits separate, or the report is not honest.

## 2. Evaluate and calibrate

```bash
gutcheck packs                          # confirm it loads
gutcheck eval support-triage --write    # fit temperatures, write eval.json, EVAL.md, calibration.json
```

Temperatures are fitted on the calibration split and the report is computed on the test split. Commit the generated files with the pack.

## 3. Guard it in CI

```bash
gutcheck eval --check
```

Fails when calibrated accuracy drops more than 0.02 or ECE rises more than 0.03 against the committed `eval.json`.

## 4. Use it

```json
{"state": "My site is down and customers are complaining", "questions": {}, "packs": ["support-triage@1"]}
```

Answers come back as `support-triage.urgent`.

## Tips

- Start with the base model, read the eval, and only fine-tune if accuracy is the limit. See [Fine-tune a pack model](/docs/guides/fine-tuning).
- Bump `version` whenever question wording changes, so old and new results stay comparable.
- Quote YAML label keys. Unquoted `yes` and `no` become booleans.

---
title: Demos
aside: false
---

# Demos

Interactive walkthroughs of what gutcheck does. Demos marked illustrative use hand-picked values to show behaviour. The measured results section uses real numbers from the committed evals.

## Decision playground

Ask typed questions, then move the thresholds and watch verdicts change. The probabilities stay fixed, which is the point: the model's belief and your risk appetite are separate things.

<Playground />

## Calibration lab

A model can be right and still sound too sure. Temperature scaling fixes the sound without changing the answer.

<CalibrationLab />

## The feedback loop

<FeedbackLoop />

## Question packs

<PackExplorer />

## Measured results

The bundled prompt-guard pack, base model against the fine-tuned checkpoint. Fine-tuning is what moves most answers from "escalate" to "act".

<EvalCompare />

More detail, including the exact datasets and revisions, is on the [prompt-guard page](/docs/packs/prompt-guard).

## Run the real thing

```bash
docker build -t gutcheck . && docker run -p 8080:8080 -v gutcheck-data:/data gutcheck
curl localhost:8080/v1/packs
```

Then open `http://localhost:8080/dashboard`. Full setup is in the [quickstart](/docs/getting-started).

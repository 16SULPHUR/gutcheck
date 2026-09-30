---
title: Demos
aside: false
---

# Live demos

Everything on this page runs the real model. Each result is a live call to a public gutcheck server, with nothing simulated, replayed or hand-picked.

<LiveDemo />

## What to try

- **Prompt guard.** Paste a normal question, an instruction override, a persona jailbreak, and a message that only talks about prompt injection. The last one is a good stress test: it mentions the attack without being one.
- **Move the thresholds.** The sliders change `act_at` and `review_at`, and the request is re-run. The model's probabilities barely change; the verdict follows your risk appetite.
- **Ask your own question.** Switch tabs, write any yes/no or multiple-choice question about any text, and see how the untuned Laya base model handles it. Compare its confidence with the fine-tuned prompt-guard checkpoint.
- **Read the raw response.** Open "Raw request and response" to see exactly what `/v1/decide` returned, including the trace id and inference latency.

## Measured results

The bundled prompt-guard pack, base model against the fine-tuned checkpoint, on test rows neither was trained or calibrated on. These are the committed eval numbers, not a demo.

<EvalCompare />

Datasets, revisions and the full reports are on the [prompt-guard page](/docs/packs/prompt-guard).

## Limits of the public demo

- It runs on a shared free CPU server, so latency is hundreds of milliseconds to seconds and the first request after idle is slower. A GPU brings it to about 30 ms.
- Inputs are capped at 2,000 characters and each visitor is rate limited. Nothing you type is stored.
- Only `/v1/decide` is open. Feedback, recalibration and the dashboard are disabled on the public server, so they are not demoed here.

## Run the real thing

```bash
docker build -t gutcheck . && docker run -p 8080:8080 -v gutcheck-data:/data gutcheck
curl localhost:8080/v1/packs
```

Then open `http://localhost:8080/dashboard`. Full setup is in the [quickstart](/docs/getting-started).

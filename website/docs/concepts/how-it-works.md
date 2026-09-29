# How it works

gutcheck sits between your app and a small classifier called [Laya](https://huggingface.co/convaiinnovations/laya). Laya scores options. gutcheck makes those scores trustworthy and turns them into decisions.

## Why a classifier

An LLM generates text one token at a time, so even a one-word answer needs a big model. A classifier maps input to a fixed set of answers in one forward pass. When the answers are known in advance (yes or no, one of five departments, a 1 to 5 score), it is far cheaper, and the output is a real probability you can threshold. Laya runs in about 33 ms on a GPU, per its authors.

The catch is that a small model is sometimes wrong, and its raw probabilities are not reliable. gutcheck adds the layer that fixes that.

## What Laya does

Laya is a cross-encoder built on ModernBERT (English, about 421M parameters) or mmBERT (multilingual, about 322M). The question, the options and the text are encoded together as one sequence, with a `[MASK]` marker per option. A small head reads each marker and outputs one score per option, and softmax turns the scores into probabilities. Because each option is scored at its own marker, the same model handles two options or two hundred.

## Request path

Every `/v1/decide` call runs the same six steps:

1. **Expand packs.** `"packs": ["prompt-guard@2"]` adds that pack's questions, each with its own temperature and policy.
2. **Route.** Questions without their own checkpoint go to Laya's router, which detects the language and picks the English or multilingual model. At most two models stay in memory, which fits 4 GB of VRAM. Pack questions with a `model:` run on that fine-tuned checkpoint instead.
3. **Predict.** One forward pass, run in a thread pool so the server stays responsive.
4. **Calibrate.** Rescale by the best temperature available: learned from feedback, else the pack's shipped value, else 1.0.
5. **Verdict.** Compare the answer probability to `act_at` and `review_at`.
6. **Log.** Store the decision under a `trace_id` in SQLite and update Prometheus metrics.

Later, `POST /v1/feedback` attaches the true answer to a `trace_id`, and `POST /v1/calibrate` refits temperatures from those labels.

## Two endpoints, two audiences

| Endpoint | Returns | For |
| --- | --- | --- |
| `POST /v1/systemone` | Laya's raw answers, no verdicts | Drop-in for Jev and `laya-serve` clients |
| `POST /v1/decide` | Calibrated answers plus verdicts, and packs | New integrations |

## Jev, Laya and gutcheck

Jev is TypeSafe AI's closed, API-only classifier. Laya, from Convai Innovations, is an Apache-2.0 model with the same interface. gutcheck is an independent open-source gateway built on Laya. It is not affiliated with either company. Base Laya checkpoints are close to chance on unfamiliar tasks, which is why gutcheck adds calibration, published evals and fine-tuning rather than trusting the raw model.

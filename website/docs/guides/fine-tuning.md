# Fine-tune a pack model

Base Laya checkpoints are trained for general typed decisions and can be near chance on your task. Fine-tuning on a pack's own training data is the biggest single quality lever. For prompt-guard it took injection accuracy from 64% to 95%.

## What it does

`gutcheck finetune` trains one Laya checkpoint on all of a pack's questions at once, then:

1. Holds out 20% of rows (fixed seed, so reruns match) to measure the result and fit temperatures.
2. Trains for 4 epochs with cross-entropy plus a reward term from Laya's RLCD recipe, which encourages honest probabilities.
3. Fits a new temperature per question type on the held-out rows.
4. Writes the checkpoint, a model card, the held-out rows and a ready-to-use `pack/` at version + 1.

The test split is never touched, so the final eval is honest.

## Run it

```bash
gutcheck finetune prompt-guard --out ./laya-prompt-guard --push you/laya-prompt-guard   # needs $HF_TOKEN
```

You need a GPU. No GPU? [`training/prompt_guard_kaggle.ipynb`](https://github.com/16SULPHUR/gutcheck/blob/master/training/prompt_guard_kaggle.ipynb) runs the same thing on Kaggle's free T4s. A 4 GB laptop GPU cannot fit full fine-tuning of a 400M-parameter model, but can serve the result.

## Use the result

The output includes `pack/<id>/pack.yaml` pointing at your checkpoint:

```yaml
model: {repo: you/laya-prompt-guard, revision: <commit>}   # or a local directory
```

Pin a commit so a later push to the Hub cannot silently change what you serve. Add the `pack/` directory to `packs.dirs`, then re-evaluate:

```bash
gutcheck eval prompt-guard@2 --write
```

Questions from that pack now run on your checkpoint, and `/v1/decide` reports it as the answer's `model`.

## Settings that matter

| Setting | Value | Why |
| --- | --- | --- |
| Base | `english` | Most data is English. `--base multilingual` switches |
| Encoder learning rate | 2.5e-5 | Gentle, keeps pre-trained knowledge |
| Head learning rate | 1e-4 | The scoring head adapts faster |
| Batch | 8 x 4 accumulation | Fits a 16 GB T4 with checkpointing |
| Precision | fp16 autocast | Half the memory, faster on T4 tensor cores |

## Judging success

Higher test accuracy than your baseline, and a larger share of `act` answers that stay correct. If held-out accuracy jumps but test accuracy barely moves, the model overfit the training distribution.

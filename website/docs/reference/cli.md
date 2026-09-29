# CLI

| Command | Does |
| --- | --- |
| `gutcheck serve` | Run the HTTP gateway. Flags: `--config`, `--host`, `--port`, `--log-level` |
| `gutcheck config` | Print the resolved configuration as JSON |
| `gutcheck packs` | List installed question packs |
| `gutcheck eval [PACK...]` | Evaluate packs against their datasets |
| `gutcheck calibrate` | Refit temperatures from feedback in the decision log |
| `gutcheck finetune PACK` | Fine-tune a Laya checkpoint on a pack's training data |

## eval

```bash
gutcheck eval support-triage --write   # fit temperatures, write eval.json, EVAL.md, calibration.json
gutcheck eval --check                  # exit 1 if accuracy or ECE regressed
```

| Flag | Meaning |
| --- | --- |
| `--calibrate` | Refit temperatures on the calibration split |
| `--write` | Write `eval.json`, `EVAL.md` and `calibration.json` into each pack directory |
| `--check` | Exit 1 if results fall below the committed baseline |
| `--summary FILE` | Write a Markdown summary of the run |
| `--cache-dir DIR` | Where downloaded datasets are kept |

## calibrate

`--min-samples N` sets how many labels a question needs before it is refit.

## finetune

```bash
gutcheck finetune prompt-guard --out ./laya-prompt-guard --push you/laya-prompt-guard
```

| Flag | Meaning |
| --- | --- |
| `--out DIR` | Required. Directory for the checkpoint |
| `--base` | `english` (default) or `multilingual` |
| `--epochs N` | Default 4 |
| `--device` | For example `cuda` |
| `--max-train`, `--max-heldout` | Cap rows per question, useful for smoke tests |
| `--push REPO` | Upload to a Hugging Face repo, using `$HF_TOKEN` |

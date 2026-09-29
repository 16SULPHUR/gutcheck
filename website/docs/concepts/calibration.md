# Calibration

A model is **calibrated** when its probabilities mean what they say: of all answers given at 0.8, about 80% are right. Neural networks are often overconfident, and act, review and escalate thresholds are meaningless without calibration.

## Temperature scaling

gutcheck fits one temperature `T` per question. Logits are divided by `T` before softmax:

- `T` above 1 flattens the distribution (less confident).
- `T` below 1 sharpens it.
- The winning option never changes, so accuracy is unchanged. Only confidence moves.

The fit tries 81 values between 0.05 and 20 and keeps the one with the lowest negative log-likelihood on labelled data, which punishes confident mistakes hard.

Try it in the [calibration lab](/demos/#calibration-lab).

## Where temperatures come from

The best available source is used, in this order:

1. **Learned** from your feedback via `/v1/calibrate`. Stored in the decision log, survives restarts.
2. **Pack** `calibration.json`, fitted on the pack's calibration split.
3. **1.0**, no change.

Learned temperatures are keyed by a fingerprint of the question's wording and options, so editing a question starts its calibration fresh.

## Measuring it

- **ECE** (expected calibration error): bucket answers by confidence, compare average confidence with actual accuracy in each bucket, take the weighted average gap. 0 is perfect.
- **Brier score**: mean squared gap between the probabilities and the one-hot truth.
- **Accuracy of act answers**: the number you care about operationally.

Every pack's eval reports these on a test split that was never used for fitting.

## Calibration is not accuracy

Calibration makes confidence honest. It cannot make a wrong model right. The prompt-guard v1 baseline shows this: after calibration, only 3.5% of injection answers were marked `act` (all correct), because the base model was right only 64% of the time. [Fine-tuning](/docs/guides/fine-tuning) raised injection accuracy to 95% and let 97% of answers be marked `act`.

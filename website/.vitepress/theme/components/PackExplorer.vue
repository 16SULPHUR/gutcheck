<script setup lang="ts">
import { ref } from 'vue'

const files = {
  'pack.yaml': `id: support-triage
version: 1
description: Routes support tickets.
questions:
  urgent:
    type: noul
    instructions: Does the customer need help within the hour?
    policy: {act_at: 0.95, review_at: 0.7}
    eval:
      test:        {path: test.jsonl,  license: CC-BY-4.0}
      calibration: {path: train.jsonl, license: CC-BY-4.0}
      text_field: text
      label_field: label
      labels: {"urgent": true, "normal": false}`,
  'gutcheck eval': `$ gutcheck eval support-triage --write

support-triage.urgent
  test rows        1,200 (never used for fitting)
  temperature      2.31 (fitted on the calibration split)
  accuracy         0.93
  ECE              0.021 (raw 0.087)

wrote eval.json  EVAL.md  calibration.json`,
  'CI gate': `$ gutcheck eval --check

fails if, against the committed eval.json:
  calibrated accuracy drops by more than 0.02
  ECE rises by more than 0.03

Runs on every pull request for the bundled packs.`,
}
const active = ref<keyof typeof files>('pack.yaml')
</script>

<template>
  <div class="gc-card pe">
    <div class="tabs">
      <button v-for="(_, name) in files" :key="name" :class="{ on: name === active }" @click="active = name">{{ name }}</button>
    </div>
    <pre>{{ files[active] }}</pre>
    <p class="gc-note">A pack is a directory: questions, the datasets that test them, a fitted calibration and a generated report. The numbers in the eval output above are an example, not a real pack.</p>
  </div>
</template>

<style scoped>
.tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.tabs button { padding: 7px 13px; border-radius: 8px; border: 1px solid var(--gc-border); background: transparent; color: var(--vp-c-text-2); cursor: pointer; font: 13px var(--vp-font-family-mono); }
.tabs button.on { background: var(--vp-c-brand-soft); border-color: var(--vp-c-brand-1); color: var(--vp-c-brand-1); }
pre { background: var(--vp-code-block-bg); border-radius: 10px; padding: 14px 16px; font: 12.5px/1.6 var(--vp-font-family-mono); overflow-x: auto; margin: 14px 0 8px; min-height: 230px; }
</style>

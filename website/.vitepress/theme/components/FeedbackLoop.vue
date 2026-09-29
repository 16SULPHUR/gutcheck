<script setup lang="ts">
import { computed, ref } from 'vue'
import { withBase } from 'vitepress'

const steps = [
  {
    title: '1. Decide',
    text: 'Your app asks a question. gutcheck answers and logs the raw probabilities under a trace id.',
    code: `curl localhost:8080/v1/decide -d '{
  "state": "Please cancel my order",
  "questions": {"urgent": {"type": "noul",
    "instructions": "Is this urgent?"}}
}'

{ "trace_id": "gc_4f9c...",
  "answers": {"urgent": {"noul": 0.81, "verdict": "review"}} }`,
  },
  {
    title: '2. Feedback',
    text: 'A person, a rule or a downstream outcome tells you what the right answer was. Send it back.',
    code: `curl localhost:8080/v1/feedback -d '{
  "trace_id": "gc_4f9c...",
  "answers": {"urgent": {"answer": false}},
  "source": "support-agent"
}'`,
  },
  {
    title: '3. Recalibrate',
    text: 'Once a question has 30 or more labels, gutcheck refits its temperature. New decisions use it straight away and it survives restarts.',
    code: `curl -X POST localhost:8080/v1/calibrate

{ "min_samples": 30,
  "questions": [{
    "question_id": "urgent",
    "n": 48, "temperature": 3.85, "accuracy": 0.6,
    "ece_before": 0.19, "ece_after": 0.06 }] }`,
  },
  {
    title: '4. Watch',
    text: 'The built-in dashboard and Prometheus metrics show traffic, latency, the verdict mix and per-question accuracy from feedback.',
    code: '',
  },
]
const i = ref(0)
const step = computed(() => steps[i.value])
</script>

<template>
  <div class="gc-card fl">
    <div class="nav">
      <button v-for="(s, n) in steps" :key="s.title" :class="{ on: n === i, done: n < i }" @click="i = n">{{ s.title }}</button>
    </div>
    <p class="text">{{ step.text }}</p>
    <pre v-if="step.code" class="code">{{ step.code }}</pre>
    <img v-else :src="withBase('/dashboard.png')" alt="gutcheck dashboard showing decisions per hour, verdict mix and per-question accuracy" />
    <p v-if="!step.code" class="gc-note">The dashboard at <code>/dashboard</code>, from a real run.</p>
    <p v-else class="gc-note">Response values are illustrative.</p>
  </div>
</template>

<style scoped>
.nav { display: flex; gap: 8px; flex-wrap: wrap; }
.nav button { padding: 8px 14px; border-radius: 8px; border: 1px solid var(--gc-border); background: transparent; color: var(--vp-c-text-2); cursor: pointer; font-size: 14px; }
.nav button.on { background: var(--vp-c-brand-soft); border-color: var(--vp-c-brand-1); color: var(--vp-c-brand-1); }
.nav button.done { color: var(--vp-c-text-1); }
.text { margin: 16px 0 12px; font-size: 16px; }
.code { background: var(--vp-code-block-bg); border-radius: 10px; padding: 14px 16px; font: 12.5px/1.6 var(--vp-font-family-mono); overflow-x: auto; margin: 0 0 8px; }
img { width: 100%; max-width: 620px; border-radius: 10px; border: 1px solid var(--gc-border); display: block; margin-bottom: 8px; }
</style>

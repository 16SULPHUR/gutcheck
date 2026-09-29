<script setup lang="ts">
import { ref } from 'vue'

const metrics = [
  { id: 'accuracy', label: 'Accuracy', note: 'higher is better', fmt: 'pct', rows: [
    { q: 'injection', v1: 0.638, v2: 0.948 },
    { q: 'jailbreak', v1: 0.823, v2: 1.0 },
  ] },
  { id: 'act', label: 'Answers safe to act on', note: 'share marked "act" after calibration', fmt: 'pct', rows: [
    { q: 'injection', v1: 0.035, v2: 0.974 },
    { q: 'jailbreak', v1: 0.383, v2: 0.995 },
  ] },
  { id: 'ece', label: 'Calibration error (ECE)', note: 'lower is better', fmt: 'num', rows: [
    { q: 'injection', v1: 0.113, v2: 0.011 },
    { q: 'jailbreak', v1: 0.049, v2: 0.006 },
  ] },
]
const active = ref('accuracy')
const current = () => metrics.find((m) => m.id === active.value)!
const show = (v: number, fmt: string) => (fmt === 'pct' ? (v * 100).toFixed(1) + '%' : v.toFixed(3))
const width = (v: number, fmt: string) => (fmt === 'pct' ? v * 100 : v * 500) + '%'
</script>

<template>
  <div class="gc-card ev">
    <div class="tabs">
      <button v-for="m in metrics" :key="m.id" :class="{ on: m.id === active }" @click="active = m.id">{{ m.label }}</button>
    </div>
    <p class="gc-note">{{ current().note }}</p>
    <div v-for="r in current().rows" :key="r.q" class="grp">
      <code>prompt-guard.{{ r.q }}</code>
      <div class="line">
        <span class="tag">v1 base</span>
        <div class="track"><div class="fill v1" :style="{ width: width(r.v1, current().fmt) }" /></div>
        <b>{{ show(r.v1, current().fmt) }}</b>
      </div>
      <div class="line">
        <span class="tag">v2 fine-tuned</span>
        <div class="track"><div class="fill v2" :style="{ width: width(r.v2, current().fmt) }" /></div>
        <b>{{ show(r.v2, current().fmt) }}</b>
      </div>
    </div>
    <p class="gc-note">Measured on held-out test splits the model never saw: deepset/prompt-injections (116 rows) and jackhhao/jailbreak-classification (400 rows). Source: the committed <a href="https://github.com/16SULPHUR/gutcheck/blob/master/src/gutcheck/packs/prompt-guard/EVAL.md">EVAL.md</a>. Bars for calibration error are scaled for visibility.</p>
  </div>
</template>

<style scoped>
.tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.tabs button { padding: 7px 13px; border-radius: 999px; border: 1px solid var(--gc-border); background: transparent; color: var(--vp-c-text-2); cursor: pointer; font-size: 14px; }
.tabs button.on { background: var(--vp-c-brand-soft); border-color: var(--vp-c-brand-1); color: var(--vp-c-brand-1); }
.grp { margin: 18px 0; }
.line { display: grid; grid-template-columns: 110px 1fr 64px; gap: 10px; align-items: center; margin-top: 8px; font-size: 14px; }
.tag { color: var(--vp-c-text-2); font-size: 13px; }
.track { height: 14px; background: var(--vp-c-default-soft); border-radius: 7px; overflow: hidden; }
.fill { height: 100%; border-radius: 7px; transition: width .4s; }
.fill.v1 { background: var(--vp-c-text-3); }
.fill.v2 { background: var(--vp-c-brand-1); }
b { text-align: right; }
</style>

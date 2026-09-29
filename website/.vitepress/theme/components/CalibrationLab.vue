<script setup lang="ts">
import { computed, ref } from 'vue'
import { softmax, verdict } from '../verdict'

const options = ['billing', 'technical', 'sales']
const logits = [3.2, 1.1, 0.4]
const temperature = ref(1)
const actAt = 0.9
const reviewAt = 0.6

const probs = computed(() => softmax(logits, temperature.value))
const top = computed(() => Math.max(...probs.value))
const v = computed(() => verdict(top.value, actAt, reviewAt))

const bins = [
  { conf: '50-60%', raw: 0.41, cal: 0.55 },
  { conf: '60-70%', raw: 0.47, cal: 0.66 },
  { conf: '70-80%', raw: 0.55, cal: 0.76 },
  { conf: '80-90%', raw: 0.62, cal: 0.86 },
  { conf: '90-100%', raw: 0.71, cal: 0.95 },
]
const showCal = ref(false)
</script>

<template>
  <div class="cal">
    <div class="gc-card">
      <div class="row">
        <div>
          <span class="lbl">Same model output, different temperature</span>
          <p class="gc-note">The encoder returned logits [3.2, 1.1, 0.4]. Divide by T, then softmax. The winner never changes; the confidence does.</p>
        </div>
        <span class="gc-badge" :class="v">{{ v }}</span>
      </div>
      <label class="t">Temperature <b>{{ temperature.toFixed(2) }}</b>
        <input class="gc-range" type="range" min="0.5" max="6" step="0.05" v-model.number="temperature" />
      </label>
      <div v-for="(o, i) in options" :key="o" class="bar">
        <span class="k">{{ o }}</span>
        <div class="track"><div class="fill" :class="{ win: probs[i] === top }" :style="{ width: probs[i] * 100 + '%' }" /></div>
        <span class="v">{{ (probs[i] * 100).toFixed(0) }}%</span>
      </div>
      <p class="gc-note">Verdict thresholds: act at 0.90, review at 0.60. T above 1 softens an overconfident model; T below 1 sharpens an underconfident one. gutcheck fits one T per question by minimising negative log-likelihood on labelled data.</p>
    </div>

    <div class="gc-card">
      <div class="row">
        <div>
          <span class="lbl">What "calibrated" means</span>
          <p class="gc-note">Of the answers given at 90-100% confidence, how many were right? Illustrative curves for an overconfident model.</p>
        </div>
        <button class="toggle" @click="showCal = !showCal">{{ showCal ? 'Showing: calibrated' : 'Showing: raw' }}</button>
      </div>
      <div class="rel">
        <div v-for="b in bins" :key="b.conf" class="col">
          <div class="pair">
            <div class="claimed" :style="{ height: (parseInt(b.conf) + 5) + '%' }" title="claimed confidence" />
            <div class="actual" :style="{ height: (showCal ? b.cal : b.raw) * 100 + '%' }" title="actual accuracy" />
          </div>
          <span class="x">{{ b.conf }}</span>
        </div>
      </div>
      <p class="gc-note"><span class="dot claimed" /> confidence claimed &nbsp; <span class="dot actual" /> accuracy achieved. When the bars match, a 0.9 really means 9 in 10.</p>
    </div>
  </div>
</template>

<style scoped>
.cal { display: grid; gap: 16px; }
.row { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.row p { margin: 4px 0 0; }
.lbl { font: 600 11px var(--vp-font-family-mono); text-transform: uppercase; letter-spacing: .08em; color: var(--vp-c-text-3); }
.t { display: block; margin: 14px 0; font-size: 14px; }
.bar { display: grid; grid-template-columns: 76px 1fr 40px; gap: 8px; align-items: center; font-size: 13px; margin: 5px 0; }
.bar .v { text-align: right; }
.track { height: 10px; background: var(--vp-c-default-soft); border-radius: 5px; overflow: hidden; }
.fill { height: 100%; background: var(--vp-c-text-3); transition: width .15s; }
.fill.win { background: var(--vp-c-brand-1); }
.toggle { padding: 7px 12px; border-radius: 8px; border: 1px solid var(--gc-border); background: transparent; color: var(--vp-c-text-1); cursor: pointer; font-size: 13px; white-space: nowrap; }
.rel { display: flex; gap: 14px; align-items: flex-end; height: 180px; margin: 16px 0 6px; }
.col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
.pair { display: flex; gap: 4px; align-items: flex-end; height: calc(100% - 20px); width: 100%; justify-content: center; }
.pair div { width: 34%; border-radius: 4px 4px 0 0; transition: height .3s; }
.claimed { background: var(--vp-c-default-3); }
.actual { background: var(--vp-c-brand-1); }
.x { font-size: 11px; color: var(--vp-c-text-3); margin-top: 6px; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; vertical-align: middle; }
</style>

<script setup lang="ts">
import { withBase } from 'vitepress'
import Playground from './Playground.vue'
import EvalCompare from './EvalCompare.vue'

const features = [
  { t: 'Verdicts, not just probabilities', d: 'Every answer comes back as act, review or escalate, so your code knows what to do with it.' },
  { t: 'Calibrated by default', d: 'Temperature scaling turns raw scores into probabilities that mean what they say.' },
  { t: 'Question packs', d: 'Versioned YAML question sets with pinned datasets, published evals and a CI regression gate.' },
  { t: 'A feedback loop', d: 'Send corrections to /v1/feedback and gutcheck recalibrates from your real traffic.' },
  { t: 'Fine-tune your own', d: 'One command trains a Laya checkpoint on a pack. The free Kaggle T4 notebook is included.' },
  { t: 'Jev-compatible', d: 'Speaks the /v1/systemone protocol, so existing Laya and Jev clients only change a base URL.' },
  { t: 'Observable', d: 'Prometheus metrics, a decision log in SQLite and a built-in dashboard.' },
  { t: 'Open source', d: 'Apache 2.0, runs on your hardware. CPU is fine, a small GPU is faster.' },
]
</script>

<template>
  <div class="land">
    <section class="hero">
      <p class="eyebrow">Open-source decision gateway</p>
      <h1>Small questions deserve <span>fast, trustworthy</span> answers.</h1>
      <p class="lead">gutcheck answers typed questions about text (pick one, rate it, yes or no) with a small classifier in milliseconds, and tells your code whether each answer is safe to act on.</p>
      <div class="cta">
        <a class="gc-btn primary" :href="withBase('/docs/getting-started')">Get started</a>
        <a class="gc-btn" :href="withBase('/demos/')">See the demos</a>
        <a class="gc-btn" href="https://github.com/16SULPHUR/gutcheck">GitHub</a>
      </div>
      <pre class="install"><span>$</span> docker run -p 8080:8080 -v gutcheck-data:/data gutcheck</pre>
    </section>

    <section class="stats">
      <div><b>95%</b><span>prompt-injection accuracy after fine-tuning, up from 64%</span></div>
      <div><b>100%</b><span>jailbreak accuracy on the held-out test set, up from 82%</span></div>
      <div><b>~33 ms</b><span>per decision on a GPU, per the Laya authors</span></div>
      <div><b>322M</b><span>parameters. Runs on a laptop, not a cluster</span></div>
    </section>

    <section>
      <h2>Try it</h2>
      <p class="sub">Pick a scenario and move the thresholds. This is the real response shape of <code>/v1/decide</code>.</p>
      <Playground />
    </section>

    <section>
      <h2>Why a classifier gateway</h2>
      <div class="why">
        <div class="gc-card"><h3>LLM for everything</h3><p>Seconds of latency, real cost per call, and a free-text answer you have to parse and hope about.</p></div>
        <div class="gc-card"><h3>Raw small model</h3><p>Fast and cheap, but the probabilities are uncalibrated and nothing says when to distrust them.</p></div>
        <div class="gc-card hl"><h3>gutcheck</h3><p>Small-model speed, calibrated probabilities, a verdict per answer and a loop that improves from feedback.</p></div>
      </div>
    </section>

    <section>
      <h2>What you get</h2>
      <div class="feat">
        <div v-for="f in features" :key="f.t" class="gc-card"><h3>{{ f.t }}</h3><p>{{ f.d }}</p></div>
      </div>
    </section>

    <section>
      <h2>Measured, not promised</h2>
      <p class="sub">The bundled prompt-guard pack, before and after fine-tuning, on test rows the model never saw.</p>
      <EvalCompare />
    </section>

    <section class="final">
      <h2>Run it in five minutes</h2>
      <div class="cta">
        <a class="gc-btn primary" :href="withBase('/docs/getting-started')">Read the quickstart</a>
        <a class="gc-btn" :href="withBase('/docs/concepts/how-it-works')">How it works</a>
      </div>
    </section>
  </div>
</template>

<style scoped>
.land { max-width: 1120px; margin: 0 auto; padding: 0 24px 80px; }
section { margin-top: 72px; }
h2 { font-size: 30px; font-weight: 700; letter-spacing: -.02em; border: 0; margin: 0 0 6px; padding: 0; }
h3 { font-size: 16px; margin: 0 0 6px; }
.sub { color: var(--vp-c-text-2); margin: 0 0 20px; }
.hero { padding: 72px 0 0; margin: 0; text-align: center; }
.eyebrow { font: 600 13px var(--vp-font-family-mono); letter-spacing: .1em; text-transform: uppercase; color: var(--vp-c-brand-1); margin: 0; }
h1 { font-size: clamp(36px, 6vw, 62px); line-height: 1.05; letter-spacing: -.03em; font-weight: 800; margin: 16px auto; max-width: 820px; }
h1 span { color: var(--vp-c-brand-1); }
.lead { font-size: 19px; color: var(--vp-c-text-2); max-width: 680px; margin: 0 auto 28px; line-height: 1.55; }
.cta { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.install { display: inline-block; margin: 32px auto 0; padding: 12px 18px; background: var(--vp-code-block-bg); border-radius: 10px; font: 14px var(--vp-font-family-mono); text-align: left; max-width: 100%; overflow-x: auto; }
.install span { color: var(--vp-c-brand-1); margin-right: 8px; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stats div { border-top: 2px solid var(--vp-c-brand-1); padding-top: 12px; }
.stats b { display: block; font-size: 36px; letter-spacing: -.02em; }
.stats span { font-size: 14px; color: var(--vp-c-text-2); }
.why { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 16px; }
.why p, .feat p { margin: 0; font-size: 14px; color: var(--vp-c-text-2); line-height: 1.55; }
.hl { border-color: var(--vp-c-brand-1); background: var(--vp-c-brand-soft); }
.feat { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 16px; }
.final { text-align: center; }
.final h2 { margin-bottom: 20px; }
@media (max-width: 960px) { .stats, .feat { grid-template-columns: repeat(2, 1fr); } .why { grid-template-columns: 1fr; } }
@media (max-width: 560px) { .stats, .feat { grid-template-columns: 1fr; } }
</style>

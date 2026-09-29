<script setup lang="ts">
import { onMounted, ref } from 'vue'

const repo = '16SULPHUR/gutcheck'
const stars = ref<number | null>(null)
const key = 'gc:stars'

function format(n: number) {
  return n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + 'k' : String(n)
}

onMounted(async () => {
  try {
    const hit = sessionStorage.getItem(key)
    if (hit) {
      const { at, n } = JSON.parse(hit)
      if (Date.now() - at < 10 * 60 * 1000) {
        stars.value = n
        return
      }
    }
  } catch {}
  try {
    const res = await fetch(`https://api.github.com/repos/${repo}`)
    if (!res.ok) return
    stars.value = (await res.json()).stargazers_count
    try {
      sessionStorage.setItem(key, JSON.stringify({ at: Date.now(), n: stars.value }))
    } catch {}
  } catch {}
})
</script>

<template>
  <a class="gh" :href="`https://github.com/${repo}`" aria-label="gutcheck on GitHub" target="_blank" rel="noopener">
    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56v-2c-3.2.7-3.87-1.36-3.87-1.36-.52-1.33-1.28-1.68-1.28-1.68-1.05-.72.08-.7.08-.7 1.15.08 1.76 1.19 1.76 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.78 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5z" />
    </svg>
    <span v-if="stars !== null" class="n">
      <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor" aria-hidden="true"><path d="M8 .25l2.32 4.7 5.18.75-3.75 3.65.89 5.15L8 12.07l-4.64 2.43.89-5.15L.5 5.7l5.18-.75z" /></svg>
      {{ format(stars) }}
    </span>
  </a>
</template>

<style scoped>
.gh { display: inline-flex; align-items: center; gap: 8px; margin-left: 12px; color: var(--vp-c-text-2); text-decoration: none; transition: color .2s; }
.gh:hover { color: var(--vp-c-text-1); }
.n { display: inline-flex; align-items: center; gap: 4px; font: 600 13px var(--vp-font-family-base); }
.n svg { color: var(--gc-review); }
</style>

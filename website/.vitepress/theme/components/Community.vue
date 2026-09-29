<script setup lang="ts">
import { onMounted, ref } from 'vue'

const repo = '16SULPHUR/gutcheck'
const api = `https://api.github.com/repos/${repo}`

type Person = { login: string; avatar_url: string; html_url: string; contributions?: number }

const stars = ref<number | null>(null)
const forks = ref<number | null>(null)
const contributors = ref<Person[]>([])
const stargazers = ref<Person[]>([])
const loaded = ref(false)

async function get<T>(path: string): Promise<T> {
  const key = `gc:${path}`
  try {
    const hit = sessionStorage.getItem(key)
    if (hit) {
      const { at, data } = JSON.parse(hit)
      if (Date.now() - at < 10 * 60 * 1000) return data
    }
  } catch {}
  const res = await fetch(api + path, { headers: { Accept: 'application/vnd.github+json' } })
  if (!res.ok) throw new Error(String(res.status))
  const data = await res.json()
  try {
    sessionStorage.setItem(key, JSON.stringify({ at: Date.now(), data }))
  } catch {}
  return data
}

onMounted(async () => {
  const [info, people, fans] = await Promise.allSettled([
    get<{ stargazers_count: number; forks_count: number }>(''),
    get<Person[]>('/contributors?per_page=30'),
    get<Person[]>('/stargazers?per_page=30'),
  ])
  if (info.status === 'fulfilled') {
    stars.value = info.value.stargazers_count
    forks.value = info.value.forks_count
  }
  if (people.status === 'fulfilled') contributors.value = people.value.filter((p) => !p.login.endsWith('[bot]'))
  if (fans.status === 'fulfilled') stargazers.value = fans.value
  loaded.value = true
})
</script>

<template>
  <div class="community">
    <div class="counts">
      <a class="gc-card count" :href="`https://github.com/${repo}/stargazers`">
        <b>{{ stars ?? '–' }}</b><span>stars</span>
      </a>
      <a class="gc-card count" :href="`https://github.com/${repo}/graphs/contributors`">
        <b>{{ loaded ? contributors.length : '–' }}</b><span>contributors</span>
      </a>
      <a class="gc-card count" :href="`https://github.com/${repo}/forks`">
        <b>{{ forks ?? '–' }}</b><span>forks</span>
      </a>
      <a class="gc-btn primary star" :href="`https://github.com/${repo}`">Star on GitHub</a>
    </div>

    <div v-if="contributors.length" class="group">
      <h3>Contributors</h3>
      <div class="faces">
        <a v-for="p in contributors" :key="p.login" :href="p.html_url" :title="`${p.login}${p.contributions ? ' · ' + p.contributions + ' commits' : ''}`">
          <img :src="p.avatar_url + '&s=96'" :alt="p.login" loading="lazy" />
        </a>
      </div>
    </div>

    <div v-if="stargazers.length" class="group">
      <h3>Stargazers</h3>
      <div class="faces">
        <a v-for="p in stargazers" :key="p.login" :href="p.html_url" :title="p.login">
          <img :src="p.avatar_url + '&s=96'" :alt="p.login" loading="lazy" />
        </a>
      </div>
      <p v-if="stars && stars > stargazers.length" class="gc-note">and {{ stars - stargazers.length }} more. <a :href="`https://github.com/${repo}/stargazers`">See all</a></p>
    </div>

    <p v-if="loaded && !stars && !contributors.length" class="gc-note">Live GitHub stats are unavailable right now. <a :href="`https://github.com/${repo}`">Open the repo</a>.</p>
  </div>
</template>

<style scoped>
.counts { display: flex; gap: 12px; flex-wrap: wrap; align-items: stretch; }
.count { display: flex; flex-direction: column; min-width: 130px; padding: 14px 20px; text-decoration: none !important; color: var(--vp-c-text-1); }
.count:hover { border-color: var(--vp-c-brand-1); }
.count b { font-size: 30px; letter-spacing: -.02em; line-height: 1.1; }
.count span { font-size: 13px; color: var(--vp-c-text-2); }
.star { align-self: center; margin-left: auto; }
.group { margin-top: 24px; }
.group h3 { font-size: 15px; margin: 0 0 10px; }
.faces { display: flex; flex-wrap: wrap; gap: 8px; }
.faces img { width: 44px; height: 44px; border-radius: 50%; border: 2px solid var(--gc-border); display: block; transition: transform .15s, border-color .15s; }
.faces a:hover img { transform: translateY(-2px); border-color: var(--vp-c-brand-1); }
@media (max-width: 560px) { .star { margin-left: 0; width: 100%; text-align: center; } }
</style>

import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import { h } from 'vue'
import Landing from './components/Landing.vue'
import LiveDemo from './components/LiveDemo.vue'
import EvalCompare from './components/EvalCompare.vue'
import GitHubStars from './components/GitHubStars.vue'
import './custom.css'

export default {
  extends: DefaultTheme,
  Layout: () =>
    h(DefaultTheme.Layout, null, {
      'nav-bar-content-after': () => h(GitHubStars),
    }),
  enhanceApp({ app }) {
    app.component('Landing', Landing)
    app.component('LiveDemo', LiveDemo)
    app.component('EvalCompare', EvalCompare)
  },
} satisfies Theme

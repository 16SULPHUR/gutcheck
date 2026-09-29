import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import { h } from 'vue'
import Landing from './components/Landing.vue'
import Playground from './components/Playground.vue'
import CalibrationLab from './components/CalibrationLab.vue'
import FeedbackLoop from './components/FeedbackLoop.vue'
import EvalCompare from './components/EvalCompare.vue'
import PackExplorer from './components/PackExplorer.vue'
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
    app.component('Playground', Playground)
    app.component('CalibrationLab', CalibrationLab)
    app.component('FeedbackLoop', FeedbackLoop)
    app.component('EvalCompare', EvalCompare)
    app.component('PackExplorer', PackExplorer)
  },
} satisfies Theme

import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import Landing from './components/Landing.vue'
import Playground from './components/Playground.vue'
import CalibrationLab from './components/CalibrationLab.vue'
import FeedbackLoop from './components/FeedbackLoop.vue'
import EvalCompare from './components/EvalCompare.vue'
import PackExplorer from './components/PackExplorer.vue'
import Community from './components/Community.vue'
import './custom.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('Landing', Landing)
    app.component('Playground', Playground)
    app.component('CalibrationLab', CalibrationLab)
    app.component('FeedbackLoop', FeedbackLoop)
    app.component('EvalCompare', EvalCompare)
    app.component('PackExplorer', PackExplorer)
    app.component('Community', Community)
  },
} satisfies Theme

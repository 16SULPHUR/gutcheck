import { defineConfig } from 'vitepress'

const repo = 'https://github.com/16SULPHUR/gutcheck'

export default defineConfig({
  title: 'gutcheck',
  description: 'The open-source decision gateway for AI agents and apps.',
  base: process.env.SITE_BASE ?? '/',
  cleanUrls: true,
  appearance: 'dark',
  head: [['link', { rel: 'icon', href: '/logo.svg' }]],
  themeConfig: {
    logo: '/logo.svg',
    nav: [
      { text: 'Docs', link: '/docs/getting-started', activeMatch: '/docs/' },
      { text: 'Demos', link: '/demos/', activeMatch: '/demos/' },
      { text: 'prompt-guard', link: '/docs/packs/prompt-guard' },
    ],
    search: { provider: 'local' },
    editLink: { pattern: `${repo}/edit/master/website/:path`, text: 'Edit this page on GitHub' },
    footer: { message: 'Released under the Apache 2.0 license.', copyright: 'Built on Laya by Convai Innovations. Not affiliated with Convai Innovations or TypeSafe AI.' },
    sidebar: {
      '/docs/': [
        {
          text: 'Start',
          items: [
            { text: 'Getting started', link: '/docs/getting-started' },
            { text: 'How it works', link: '/docs/concepts/how-it-works' },
          ],
        },
        {
          text: 'Concepts',
          items: [
            { text: 'Questions and types', link: '/docs/concepts/questions' },
            { text: 'Verdicts and policies', link: '/docs/concepts/verdicts' },
            { text: 'Calibration', link: '/docs/concepts/calibration' },
            { text: 'Question packs', link: '/docs/concepts/packs' },
          ],
        },
        {
          text: 'API reference',
          items: [
            { text: 'POST /v1/decide', link: '/docs/reference/decide' },
            { text: 'POST /v1/systemone', link: '/docs/reference/systemone' },
            { text: 'Feedback and calibrate', link: '/docs/reference/feedback' },
            { text: 'Packs, stats, metrics', link: '/docs/reference/ops' },
          ],
        },
        {
          text: 'Guides',
          items: [
            { text: 'Write a question pack', link: '/docs/guides/writing-a-pack' },
            { text: 'Fine-tune a pack model', link: '/docs/guides/fine-tuning' },
            { text: 'Run in production', link: '/docs/guides/deployment' },
          ],
        },
        {
          text: 'Reference',
          items: [
            { text: 'Configuration', link: '/docs/reference/configuration' },
            { text: 'CLI', link: '/docs/reference/cli' },
          ],
        },
        {
          text: 'Packs',
          items: [{ text: 'prompt-guard', link: '/docs/packs/prompt-guard' }],
        },
      ],
    },
  },
})

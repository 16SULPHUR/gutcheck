export type Verdict = 'act' | 'review' | 'escalate'

export function verdict(p: number, actAt: number, reviewAt: number): Verdict {
  if (p >= actAt) return 'act'
  if (p >= reviewAt) return 'review'
  return 'escalate'
}

export function softmax(logits: number[], temperature = 1): number[] {
  const scaled = logits.map((z) => z / temperature)
  const max = Math.max(...scaled)
  const exps = scaled.map((z) => Math.exp(z - max))
  const sum = exps.reduce((a, b) => a + b, 0)
  return exps.map((e) => e / sum)
}

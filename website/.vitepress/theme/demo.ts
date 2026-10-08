export const API = (import.meta.env.VITE_DEMO_API ?? 'https://16sulphur-gutcheck-demo.hf.space').replace(/\/$/, '')

export type Answer = {
  type: 'noul' | 'choice' | 'score'
  noul?: number
  choice?: string
  probabilities?: Record<string, number>
  answer_probability: number
  verdict: 'act' | 'review' | 'escalate'
}

export type Decision = {
  trace_id: string
  model: string
  answers: Record<string, Answer>
  latency_ms: number
}

export class DemoError extends Error {
  constructor(
    message: string,
    readonly offline = false,
  ) {
    super(message)
  }
}

export async function decide(body: unknown): Promise<{ decision: Decision; wallMs: number }> {
  const start = performance.now()
  let res: Response
  try {
    res = await fetch(`${API}/v1/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new DemoError('The live demo server is not reachable right now.', true)
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') detail = data.detail
    } catch {}
    throw new DemoError(detail, res.status >= 500 && res.status !== 503)
  }
  return { decision: await res.json(), wallMs: performance.now() - start }
}

export async function health(): Promise<{ loaded: string[] } | null> {
  try {
    const res = await fetch(`${API}/healthz`)
    if (!res.ok) return null
    return (await res.json()).engine
  } catch {
    return null
  }
}

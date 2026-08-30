import { useState } from 'react'
import { useTtsApi } from '../../api/api-context'
import type { SynthParams, SynthResult } from '../../api/types'

export type GenerateState = 'idle' | 'generating' | 'success' | 'error'
export function useGenerate() {
  const api = useTtsApi(); const [state, setState] = useState<GenerateState>('idle'); const [progress, setProgress] = useState<number | null>(null); const [result, setResult] = useState<SynthResult | null>(null)
  async function generate(params: SynthParams) { setState('generating'); setResult(null); setProgress(params.text.length > 1200 ? 0 : null); try { const next = params.text.length > 1200 ? await api.synthStream(params, setProgress) : await api.synth(params); setResult(next); setState('success') } catch { setState('error') } }
  return { state, progress, result, generate, reset: () => { setState('idle'); setProgress(null); setResult(null) } }
}

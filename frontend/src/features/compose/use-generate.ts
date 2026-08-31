import { useState } from 'react'
import { useTtsApi } from '../../api/api-context'
import type { SynthParams, SynthResult } from '../../api/types'

import { mapErrorToLimitKind } from '../../api/error-map'
import type { LimitKind } from '../../lib/limits'

export type GenerateState = 'idle' | 'generating' | 'success' | 'error'
export function useGenerate() {
  const api = useTtsApi(); const [state, setState] = useState<GenerateState>('idle'); const [progress, setProgress] = useState<number | null>(null); const [result, setResult] = useState<SynthResult | null>(null); const [error, setError] = useState<string | LimitKind>('')
  async function generate(params: SynthParams) { setState('generating'); setResult(null); setError(''); setProgress(params.text.length > 120 ? 0 : null); try { const next = params.text.length > 120 ? await api.synthStream(params, setProgress) : await api.synth(params); setResult(next); setState('success') } catch (err) { setError(mapErrorToLimitKind(err) || 'generic'); setState('error') } }
  return { state, progress, result, error, generate, reset: () => { setState('idle'); setProgress(null); setResult(null); setError('') } }
}

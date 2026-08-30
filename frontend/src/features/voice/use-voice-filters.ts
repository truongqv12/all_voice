import { useMemo, useState } from 'react'
import type { Voice, VoiceLanguage } from '../../api/types'

function normalized(value: string) { return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase() }

export function useVoiceFilters(voices: Voice[]) {
  const [language, setLanguage] = useState<VoiceLanguage | 'all'>('all')
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => voices.filter(voice => (language === 'all' || voice.language === language) && normalized(`${voice.name} ${voice.styles.join(' ')}`).includes(normalized(query))), [voices, language, query])
  return { language, setLanguage, query, setQuery, filtered, reset: () => { setLanguage('all'); setQuery('') } }
}

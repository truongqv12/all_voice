import { useMemo, useState } from 'react'
import type { Voice, VoiceGender, VoiceLanguage } from '../../api/types'

function normalized(value: string) { return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase() }

export function useVoiceFilters(voices: Voice[]) {
  const [language, setLanguage] = useState<VoiceLanguage | 'all'>('all')
  const [gender, setGender] = useState<VoiceGender | 'all'>('all')
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => voices.filter(voice => (language === 'all' || voice.language === language) && (gender === 'all' || voice.gender === gender) && normalized(`${voice.name} ${voice.description} ${voice.styles.join(' ')}`).includes(normalized(query))), [voices, language, gender, query])
  return { language, setLanguage, gender, setGender, query, setQuery, filtered, reset: () => { setLanguage('all'); setGender('all'); setQuery('') } }
}

import { Cpu } from 'lucide-react'
import { useSelection } from '../../store/selection'
import { useTranslation } from 'react-i18next'
import { Select, type SelectOption } from '../../components/ui/select'

export function ModelSelect() {
  const { selectedVoice, selectVoice, voices } = useSelection()
  const { t } = useTranslation()
  if (!selectedVoice) return null

  const engines = Array.from(new Set(voices.map(voice => voice.engine)))
  const options: SelectOption[] = engines.map(engine => ({
    value: engine,
    label: engine === 'vieneu' ? 'VieNeu' : engine === 'voicevox' ? 'VOICEVOX' : 'Kokoro',
    description: engine === 'vieneu' ? 'Tiếng Việt tự nhiên' : engine === 'voicevox' ? 'Đa phong cách' : 'Siêu nhanh',
    icon: <Cpu size={15} className="shrink-0 text-[var(--color-primary)]" />,
  }))

  return (
    <div>
      <span className="block text-sm font-semibold mb-1.5">{t('compose.model')}</span>
      <Select
        value={selectedVoice.engine}
        options={options}
        onChange={val => {
          const match = voices.find(voice => voice.engine === val)
          if (match) selectVoice(match)
        }}
        aria-label={t('compose.model')}
      />
    </div>
  )
}

import { Cpu } from 'lucide-react'
import { useSelection } from '../../store/selection'
import { useTranslation } from 'react-i18next'
import { Select, type SelectOption } from '../../components/ui/select'

const ENGINE_META: Record<string, { label: string; descKey: string; defaultDesc: string }> = {
  vieneu: { label: 'VieNeu', descKey: 'compose.engine.vieneu', defaultDesc: 'Tiếng Việt tự nhiên' },
  capcut: { label: 'CapCut', descKey: 'compose.engine.capcut', defaultDesc: '24 giọng đám mây' },
  voicevox: { label: 'VOICEVOX', descKey: 'compose.engine.voicevox', defaultDesc: 'Đa phong cách' },
  kokoro: { label: 'Kokoro', descKey: 'compose.engine.kokoro', defaultDesc: 'Siêu nhanh' },
  clone: { label: 'Clone', descKey: 'compose.engine.clone', defaultDesc: 'Giọng tùy chỉnh' },
}

export function ModelSelect() {
  const { selectedVoice, selectVoice, voices } = useSelection()
  const { t } = useTranslation()
  if (!selectedVoice) return null

  const engines = Array.from(new Set(voices.map(voice => voice.engine)))
  const options: SelectOption[] = engines.map(engine => {
    const meta = ENGINE_META[engine]
    return {
      value: engine,
      label: meta ? meta.label : engine,
      description: meta ? t(meta.descKey, { defaultValue: meta.defaultDesc }) : '',
      icon: <Cpu size={15} className="shrink-0 text-[var(--color-primary)]" />,
    }
  })

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

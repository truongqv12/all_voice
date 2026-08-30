import { Sparkles } from 'lucide-react'
import { useSelection } from '../../store/selection'
import { useTranslation } from 'react-i18next'
import { Select, type SelectOption } from '../../components/ui/select'

export function StyleSelect() {
  const { selectedVoice, style, setStyle } = useSelection()
  const { t } = useTranslation()
  if (!selectedVoice) return null

  const options: SelectOption[] = selectedVoice.styles.map(item => ({
    value: item,
    label: item,
    icon: <Sparkles size={14} className="shrink-0 text-[var(--color-primary)]" />,
  }))

  return (
    <div>
      <span className="block text-sm font-semibold mb-1.5">{t('compose.style')}</span>
      <Select
        value={style}
        options={options}
        onChange={setStyle}
        aria-label={t('compose.style')}
      />
    </div>
  )
}

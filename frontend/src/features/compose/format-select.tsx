import { FileAudio } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { AudioFormat } from '../../api/types'
import { Select, type SelectOption } from '../../components/ui/select'

export function FormatSelect({ format, onChange }: { format: AudioFormat; onChange(format: AudioFormat): void }) {
  const { t } = useTranslation()

  const options: SelectOption[] = [
    { value: 'mp3', label: 'MP3', description: 'Nén chuẩn, nhẹ', icon: <FileAudio size={15} className="shrink-0 text-[var(--color-primary)]" /> },
    { value: 'wav', label: 'WAV', description: 'Lossless cao cấp', icon: <FileAudio size={15} className="shrink-0 text-[var(--color-primary)]" /> },
    { value: 'ogg', label: 'OGG', description: 'Tối ưu web', icon: <FileAudio size={15} className="shrink-0 text-[var(--color-primary)]" /> },
  ]

  return (
    <div>
      <span className="block text-sm font-semibold mb-1.5">{t('compose.format')}</span>
      <Select
        value={format}
        options={options}
        onChange={val => onChange(val as AudioFormat)}
        aria-label={t('compose.format')}
      />
    </div>
  )
}

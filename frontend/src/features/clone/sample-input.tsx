import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/button'
import { RecordButton } from './record-button'

export function SampleInput({ onChange }: { onChange(name: string): void }) {
  const { t } = useTranslation(); const input = useRef<HTMLInputElement>(null); const [name, setName] = useState('')
  function select(file?: File) { if (!file) return; if (!/\.(mp3|wav)$/iu.test(file.name)) { setName(t('clone.sampleError')); return }; setName(file.name); onChange(file.name) }
  function recorded(label: string) { setName(label); onChange(label) }
  return <fieldset className="grid gap-3"><legend className="text-sm font-semibold">{t('clone.sampleLabel')}</legend><p className="text-sm leading-6 text-[var(--color-muted)]">{t('clone.sampleHint')}</p><div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => input.current?.click()}>{t('clone.chooseSample')}</Button><RecordButton onReady={recorded} /></div><input ref={input} className="sr-only" type="file" accept=".mp3,.wav,audio/mpeg,audio/wav" onChange={event => select(event.target.files?.[0])} />{name && <p aria-live="polite" className="text-sm text-[var(--color-primary)]">{name}</p>}</fieldset>
}

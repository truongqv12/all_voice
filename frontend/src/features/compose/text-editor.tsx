import { useTranslation } from 'react-i18next'

export function TextEditor({ value, onChange }: { value: string; onChange(value: string): void }) {
  const { t } = useTranslation()
  return <label className="block"><span className="text-sm font-semibold">{t('compose.textLabel')}</span><textarea value={value} onChange={event => onChange(event.target.value)} className="mt-2 min-h-52 w-full resize-y rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-base leading-7 text-[var(--color-text)] placeholder:text-[var(--color-muted)] focus-visible:border-[var(--color-primary)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid" placeholder={t('compose.placeholder')} /></label>
}

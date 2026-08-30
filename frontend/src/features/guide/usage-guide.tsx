import { ChevronDown, Lightbulb } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

export function UsageGuide() {
  const { t } = useTranslation(); const [open, setOpen] = useState(false)
  return <section className="rounded-[var(--radius-panel)] border border-[var(--color-border)] bg-[var(--color-surface-soft)]"><button aria-expanded={open} onClick={() => setOpen(value => !value)} className="flex min-h-11 w-full cursor-pointer items-center gap-3 px-4 py-3 text-left"><Lightbulb className="text-[var(--color-primary)]" size={18} /><span className="grow font-semibold">{t('guide.title')}</span><ChevronDown className={open ? 'rotate-180 transition-transform' : 'transition-transform'} size={18} /></button>{open && <div className="border-t border-[var(--color-border)] px-4 py-4 text-sm leading-6 text-[var(--color-muted)]"><p>{t('guide.intro')}</p><ul className="mt-3 list-disc space-y-2 pl-5"><li>{t('guide.tipNumbers')}</li><li>{t('guide.tipAbbreviations')}</li><li>{t('guide.useCases')}</li></ul></div>}</section>
}

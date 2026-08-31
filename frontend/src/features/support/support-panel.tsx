import { Check, CheckCircle2, Clipboard, Code2, ExternalLink, HandHeart, Info, Lightbulb, Sliders } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { appConfig } from '../../config/app-config'
import { Button } from '../../components/ui/button'

export function SupportPanel() {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  async function copyBank() {
    await navigator.clipboard.writeText('Vietcombank - 1062811353')
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-4">
      {/* SECTION 1: VietQR & Community Donate */}
      <section className="rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div className="flex items-start gap-2.5">
          <div className="grid size-8 shrink-0 place-items-center rounded-md bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
            <HandHeart size={18} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[var(--color-text)]">{t('support.donateTitle')}</h3>
            <p className="mt-1 text-xs leading-5 text-[var(--color-muted)]">{t('support.donateDesc')}</p>
          </div>
        </div>

        <div className="mt-4 flex flex-col items-center gap-3 rounded-[var(--radius-control)] border border-dashed border-[var(--color-border)] bg-[var(--color-surface-soft)] p-3 text-center sm:flex-row sm:text-left">
          <img
            src="https://img.vietqr.io/image/vcb-1062811353-qr_only.png"
            alt="VietQR"
            className="size-24 shrink-0 rounded border border-[var(--color-border)] bg-white object-contain p-1 shadow-xs"
          />

          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-[var(--color-text)]">{t('support.qrTitle')}</p>
            <p className="mt-0.5 text-xs text-[var(--color-muted)]">{t('support.bankInfo')}</p>

            <div className="mt-2.5 flex flex-wrap gap-2">
              <Button variant="secondary" className="px-2.5 py-1 text-xs" onClick={() => void copyBank()}>
                {copied ? <Check className="shrink-0 text-[var(--color-primary)]" size={14} /> : <Clipboard className="shrink-0" size={14} />}
                <span>{copied ? t('support.copiedBank') : t('support.copyBank')}</span>
              </Button>
              <a href={appConfig.support.buyMeCoffeeUrl} target="_blank" rel="noreferrer">
                <Button variant="secondary" className="px-2.5 py-1 text-xs">
                  <ExternalLink className="shrink-0" size={14} />
                  <span>{t('support.bmc')}</span>
                </Button>
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 2: Standard Service Capacity & Limits */}
      <section className="rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] p-4">
        <div className="flex items-start gap-2.5">
          <div className="grid size-8 shrink-0 place-items-center rounded-md bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
            <Sliders size={18} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[var(--color-text)]">{t('support.whyLimitsTitle')}</h3>
            <p className="mt-1 text-xs leading-5 text-[var(--color-muted)]">{t('support.whyLimitsDesc')}</p>
          </div>
        </div>

        <div className="mt-3 space-y-2 border-t border-[var(--color-border)] pt-3 text-xs text-[var(--color-text)]">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-[var(--color-primary)]" />
            <span className="leading-5">{t('support.limitsRule1')}</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-[var(--color-primary)]" />
            <span className="leading-5">{t('support.limitsRule2')}</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-[var(--color-primary)]" />
            <span className="leading-5">{t('support.limitsRule3')}</span>
          </div>
        </div>
      </section>

      {/* SECTION 3: Tips for Natural Audio Synthesis */}
      <section className="rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div className="flex items-start gap-2.5">
          <div className="grid size-8 shrink-0 place-items-center rounded-md bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
            <Lightbulb size={18} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[var(--color-text)]">{t('support.serverSpecTitle')}</h3>
            <p className="mt-1 text-xs leading-5 text-[var(--color-muted)]">{t('support.serverSpecDesc')}</p>
          </div>
        </div>
      </section>

      {/* SECTION 4: Open Source & Self-Host Option */}
      <section className="rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] p-4">
        <div className="flex items-start gap-2.5">
          <div className="grid size-8 shrink-0 place-items-center rounded-md bg-[var(--color-surface)] text-[var(--color-muted)]">
            <Code2 size={18} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[var(--color-text)]">{t('support.selfHostTitle')}</h3>
            <p className="mt-1 text-xs leading-5 text-[var(--color-muted)]">{t('support.selfHostDesc')}</p>
            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer"
              className="mt-2.5 inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--color-primary)] hover:underline"
            >
              <Info size={14} className="shrink-0" />
              <span>{t('support.selfHostAction')}</span>
              <ExternalLink size={12} className="shrink-0" />
            </a>
          </div>
        </div>
      </section>
    </div>
  )
}

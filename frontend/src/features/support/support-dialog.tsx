import { Info, X } from 'lucide-react'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { IconButton } from '../../components/ui/icon-button'
import { SupportPanel } from './support-panel'

interface Props {
  open: boolean
  onClose(): void
}

export function SupportDialog({ open, onClose }: Props) {
  const { t } = useTranslation()

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && open) onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="support-dialog-title"
        className="relative z-10 max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[var(--radius-panel)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-xl sm:p-6"
      >
        <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
          <div className="flex items-center gap-2">
            <Info className="text-[var(--color-primary)] shrink-0" size={20} />
            <h2 id="support-dialog-title" className="text-base font-bold text-[var(--color-text)]">
              {t('support.title')}
            </h2>
          </div>
          <IconButton onClick={onClose} aria-label={t('support.dismiss')}>
            <X size={18} />
          </IconButton>
        </div>

        <div className="mt-4">
          <SupportPanel />
        </div>
      </div>
    </div>
  )
}

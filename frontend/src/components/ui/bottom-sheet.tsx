import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { IconButton } from './icon-button'
import { useTranslation } from 'react-i18next'

interface BottomSheetProps { open: boolean; onOpenChange(open: boolean): void; title: string; children: ReactNode }

export function BottomSheet({ open, onOpenChange, title, children }: BottomSheetProps) {
  const { t } = useTranslation()
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/55" /><Dialog.Content className="fixed inset-x-0 bottom-0 z-50 flex max-h-[85dvh] flex-col rounded-t-[var(--radius-panel)] border border-[var(--color-border)] bg-[var(--color-surface)] pb-[env(safe-area-inset-bottom)] shadow-none"><div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3"><Dialog.Title className="text-base font-semibold">{title}</Dialog.Title><Dialog.Close asChild><IconButton aria-label={t('a11y.close')}><X size={20} /></IconButton></Dialog.Close></div><div className="min-h-0 overflow-y-auto overscroll-contain p-4">{children}</div></Dialog.Content></Dialog.Portal></Dialog.Root>
}

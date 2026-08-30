import { Trash2, UserRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { VoiceClone } from '../../api/clone-api'
import { mockCloneApi } from '../../api/clone-api'
import { Button } from '../../components/ui/button'

export function MyClonesList({ clones, onDeleted }: { clones: VoiceClone[]; onDeleted(id: string): void }) {
  const { t } = useTranslation()
  async function remove(clone: VoiceClone) { if (!window.confirm(t('clone.deleteConfirm', { name: clone.name }))) return; await mockCloneApi.deleteClone(clone.id); onDeleted(clone.id) }
  return <section className="rounded-[var(--radius-panel)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:p-6"><h2 className="text-xl font-bold">{t('clone.myClones')}</h2>{!clones.length ? <div className="mt-4 rounded-[var(--radius-control)] bg-[var(--color-surface-soft)] p-5 text-sm text-[var(--color-muted)]">{t('clone.empty')}</div> : <ul className="mt-4 space-y-2">{clones.map(clone => <li key={clone.id} className="flex items-center gap-3 rounded-[var(--radius-control)] border border-[var(--color-border)] p-3"><UserRound className="shrink-0 text-[var(--color-primary)]" size={18} /><div className="min-w-0 flex-1"><p className="truncate font-semibold">{clone.name}</p><p className="text-xs text-[var(--color-muted)]">{clone.createdAt} · {t('clone.ready')}</p></div><Button aria-label={t('clone.delete', { name: clone.name })} variant="quiet" className="px-3 text-[var(--color-danger)]" onClick={() => void remove(clone)}><Trash2 size={17} /></Button></li>)}</ul>}</section>
}

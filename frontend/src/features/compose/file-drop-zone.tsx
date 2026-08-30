import { useState } from 'react'
import { useTranslation } from 'react-i18next'

export function FileDropZone({ onText, className = '' }: { onText(text: string): void; className?: string }) {
  const { t } = useTranslation(); const [dragging, setDragging] = useState(false); const [message, setMessage] = useState('')
  async function read(file?: File) { if (!file) return; if (!file.name.toLowerCase().endsWith('.txt')) { setMessage(t('compose.fileError')); return }; onText(await file.text()); setMessage(t('compose.fileLoaded', { name: file.name })) }
  return <label onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); void read(event.dataTransfer.files[0]) }} className={`flex min-h-11 cursor-pointer items-center justify-between rounded-[var(--radius-control)] border px-3 text-sm ${dragging ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]' : 'border-dashed border-[var(--color-border)] bg-[var(--color-surface)]/95 text-[var(--color-muted)]'} ${className}`}><span>{t('compose.fileHint')}</span><input className="sr-only" type="file" accept=".txt,text/plain" onChange={event => void read(event.target.files?.[0])} />{message && <span className="ml-3 truncate text-xs">{message}</span>}</label>
}

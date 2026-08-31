import { AudioLines, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/button'

export function AudioDropZone({ onFile, error, disabled = false }: { onFile(file: File): void; error: string; disabled?: boolean }) {
  const { t } = useTranslation()
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function accept(file?: File) {
    if (!disabled && file) onFile(file)
  }

  const message = error ? t(`transcribe.error.${error}`) : ''

  return (
    <section
      onDragOver={event => {
        if (!disabled) {
          event.preventDefault()
          setDragging(true)
        }
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={event => {
        if (!disabled) {
          event.preventDefault()
          setDragging(false)
          accept(event.dataTransfer.files[0])
        }
      }}
      className={`rounded-[var(--radius-panel)] border border-dashed p-6 text-center sm:p-10 ${
        dragging
          ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]'
          : 'border-[var(--color-border)] bg-[var(--color-surface)]'
      } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
    >
      <AudioLines className="mx-auto text-[var(--color-primary)]" size={32} />
      <h2 className="mt-4 text-2xl font-bold tracking-[-0.02em]">{t('transcribe.uploadTitle')}</h2>
      <p className="mx-auto mt-2 max-w-lg leading-7 text-[var(--color-muted)]">
        {t('transcribe.uploadDescription')}
      </p>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <Button disabled={disabled} onClick={() => input.current?.click()}>
          <Upload className="shrink-0" size={17} />
          <span>{t('transcribe.chooseFile')}</span>
        </Button>
      </div>

      <input
        ref={input}
        className="sr-only"
        type="file"
        disabled={disabled}
        accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/x-m4a"
        onChange={event => accept(event.target.files?.[0])}
      />
      {message && (
        <p role="alert" className="mx-auto mt-4 max-w-lg rounded-[var(--radius-control)] border border-[var(--color-danger)] p-3 text-sm text-[var(--color-danger)]">
          {message}
        </p>
      )}
    </section>
  )
}

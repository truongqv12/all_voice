import type { AudioFormat } from '../../api/types'
import { StyleSelect } from './style-select'
import { FormatSelect } from './format-select'

export function SynthControls({ format, onFormat }: { format: AudioFormat; onFormat(format: AudioFormat): void }) {
  return <div className="grid gap-3 border-t border-[var(--color-border)] pt-4 sm:grid-cols-2"><StyleSelect /><FormatSelect format={format} onChange={onFormat} /></div>
}

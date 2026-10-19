import type { AudioFormat } from '../../api/types'
import { ModelSelect } from './model-select'
import { StyleSelect } from './style-select'
import { FormatSelect } from './format-select'

export function SynthControls({ format, onFormat }: { format: AudioFormat; onFormat(format: AudioFormat): void }) {
  return <div className="grid gap-3 border-t border-[var(--color-border)] pt-4 sm:grid-cols-3"><ModelSelect /><StyleSelect /><FormatSelect format={format} onChange={onFormat} /></div>
}

import type { AudioFormat } from '../../api/types'
import { ModelSelect } from './model-select'
import { StyleSelect } from './style-select'
import { SpeedSlider } from './speed-slider'
import { FormatSelect } from './format-select'

export function SynthControls({ speed, format, onSpeed, onFormat }: { speed: number; format: AudioFormat; onSpeed(speed: number): void; onFormat(format: AudioFormat): void }) { return <div className="grid gap-3 border-t border-[var(--color-border)] pt-4 sm:grid-cols-2"><ModelSelect /><StyleSelect /><SpeedSlider speed={speed} onChange={onSpeed} /><FormatSelect format={format} onChange={onFormat} /></div> }

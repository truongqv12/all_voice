import type { AudioFormat } from '../../api/types'
import { StyleSelect } from './style-select'
import { SpeedSlider } from './speed-slider'
import { FormatSelect } from './format-select'
import { useSelection } from '../../store/selection'

export function SynthControls({ speed, format, onSpeed, onFormat }: { speed: number; format: AudioFormat; onSpeed(speed: number): void; onFormat(format: AudioFormat): void }) {
  const { selectedVoice } = useSelection();
  return <div className="grid gap-3 border-t border-[var(--color-border)] pt-4 sm:grid-cols-2"><StyleSelect />{selectedVoice?.engine !== 'vieneu' && <SpeedSlider speed={speed} onChange={onSpeed} />}<FormatSelect format={format} onChange={onFormat} /></div>
}

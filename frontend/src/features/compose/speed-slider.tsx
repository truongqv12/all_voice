import { useTranslation } from 'react-i18next'
import { Slider } from '../../components/ui/slider'

export function SpeedSlider({ speed, onChange }: { speed: number; onChange(speed: number): void }) { const { t } = useTranslation(); return <label className="block text-sm font-semibold">{t('compose.speed')} <span className="float-right tabular-nums text-[var(--color-muted)]">{speed.toFixed(2)}×</span><Slider value={[speed]} onValueChange={value => onChange(value[0])} min={0.25} max={4} step={0.05} label={t('compose.speed')} /></label> }

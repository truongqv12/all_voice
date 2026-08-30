import * as SliderPrimitive from '@radix-ui/react-slider'

interface SliderProps { value: number[]; onValueChange(value: number[]): void; min: number; max: number; step: number; label: string }

export function Slider({ value, onValueChange, min, max, step, label }: SliderProps) {
  return <SliderPrimitive.Root className="flex min-h-11 w-full touch-none items-center" value={value} onValueChange={onValueChange} min={min} max={max} step={step} aria-label={label}>
    <SliderPrimitive.Track className="relative h-1.5 grow rounded-full bg-[var(--color-border)]"><SliderPrimitive.Range className="absolute h-full rounded-full bg-[var(--color-primary)]" /></SliderPrimitive.Track>
    <SliderPrimitive.Thumb className="block size-5 rounded-full border-2 border-[var(--color-surface)] bg-[var(--color-primary)] shadow-sm" />
  </SliderPrimitive.Root>
}

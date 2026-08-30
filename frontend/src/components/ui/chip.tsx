import type { ButtonHTMLAttributes } from 'react'

export function Chip({ selected = false, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean }) {
  const state = selected ? 'border-2 border-[var(--color-primary)] bg-[var(--color-primary-soft)] text-[var(--color-primary)] font-semibold' : 'border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-muted)] hover:text-[var(--color-text)]'
  return <button className={`min-h-11 cursor-pointer rounded-full px-3.5 text-sm transition-[transform,background-color,color,border-color] duration-200 ease-[var(--ease-ui)] active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid ${state} ${className}`} aria-pressed={selected} {...props} />
}

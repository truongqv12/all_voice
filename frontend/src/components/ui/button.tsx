import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'quiet' | 'danger'
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

const styles: Record<Variant, string> = {
  primary: 'bg-[var(--color-primary)] text-[var(--color-primary-foreground)] hover:bg-[var(--color-primary-hover)] border border-transparent',
  secondary: 'border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] hover:bg-[var(--color-surface-soft)]',
  quiet: 'text-[var(--color-muted)] hover:bg-[var(--color-surface-soft)] hover:text-[var(--color-text)] border border-transparent',
  danger: 'bg-[var(--color-danger)] text-[var(--color-surface)] hover:opacity-90 border border-transparent',
}

export function Button({ className = '', type = 'button', variant = 'primary', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex min-h-11 items-center justify-center gap-2 whitespace-nowrap select-none cursor-pointer rounded-[var(--radius-control)] px-4 py-2 text-sm font-semibold transition-[transform,background-color,color,border-color,opacity] duration-200 ease-[var(--ease-ui)] active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid disabled:cursor-not-allowed disabled:bg-[var(--color-surface-soft)] disabled:text-[var(--color-muted)] disabled:border disabled:border-[var(--color-border)] disabled:active:scale-100 ${styles[variant]} ${className}`}
      {...props}
    />
  )
}

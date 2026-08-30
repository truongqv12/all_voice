import type { ButtonHTMLAttributes, ReactNode } from 'react'

export function IconButton({ children, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return <button className={`grid size-11 cursor-pointer place-items-center rounded-[var(--radius-control)] text-[var(--color-muted)] transition-[transform,background-color,color] duration-200 ease-[var(--ease-ui)] hover:bg-[var(--color-surface-soft)] hover:text-[var(--color-text)] active:scale-[0.96] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid ${className}`} {...props}>{children}</button>
}

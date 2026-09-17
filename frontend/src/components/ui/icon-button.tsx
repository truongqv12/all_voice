import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Size = 'default' | 'sm' | 'xs'

const sizeStyles: Record<Size, string> = {
  default: 'size-11',
  sm: 'size-9',
  xs: 'size-7',
}

export function IconButton({ children, className = '', size = 'default', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode; size?: Size }) {
  return <button className={`grid ${sizeStyles[size]} cursor-pointer place-items-center rounded-[var(--radius-control)] text-[var(--color-muted)] transition-[transform,background-color,color] duration-200 ease-[var(--ease-ui)] hover:bg-[var(--color-surface-soft)] hover:text-[var(--color-text)] active:scale-[0.96] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid ${className}`} {...props}>{children}</button>
}

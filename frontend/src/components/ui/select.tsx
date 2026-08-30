import { Check, ChevronDown, Search } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'

export interface SelectOption {
  value: string
  label: string
  description?: string
  icon?: ReactNode
}

interface SelectProps {
  value: string
  options: SelectOption[]
  onChange(value: string): void
  placeholder?: string
  searchable?: boolean
  searchPlaceholder?: string
  className?: string
  'aria-label'?: string
}

export function Select({
  value,
  options,
  onChange,
  placeholder,
  searchable = false,
  searchPlaceholder = 'Tìm kiếm...',
  className = '',
  'aria-label': ariaLabel,
}: SelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const listboxId = useRef(`select-listbox-${Math.random().toString(36).slice(2, 9)}`).current

  const selectedOption = options.find(opt => opt.value === value)

  const filteredOptions = searchable && query.trim()
    ? options.filter(
        opt =>
          opt.label.toLowerCase().includes(query.toLowerCase()) ||
          opt.description?.toLowerCase().includes(query.toLowerCase()) ||
          opt.value.toLowerCase().includes(query.toLowerCase())
      )
    : options

  useEffect(() => {
    let focusTimer: number | undefined
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      if (searchable) {
        focusTimer = window.setTimeout(() => searchInputRef.current?.focus(), 50)
      }
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      if (focusTimer) window.clearTimeout(focusTimer)
    }
  }, [open, searchable])

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === 'Escape') {
      setOpen(false)
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (!open) {
        setOpen(true)
        setActiveIndex(0)
      } else {
        setActiveIndex(prev => (prev < filteredOptions.length - 1 ? prev + 1 : 0))
      }
    } else if (event.key === 'ArrowUp' && open) {
      event.preventDefault()
      setActiveIndex(prev => (prev > 0 ? prev - 1 : filteredOptions.length - 1))
    } else if (event.key === 'Enter' && open && activeIndex >= 0 && activeIndex < filteredOptions.length) {
      event.preventDefault()
      select(filteredOptions[activeIndex].value)
    }
  }

  function select(val: string) {
    onChange(val)
    setOpen(false)
    setQuery('')
    setActiveIndex(-1)
  }

  return (
    <div ref={containerRef} className={`relative ${className}`} onKeyDown={handleKeyDown}>
      <button
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listboxId}
        aria-label={ariaLabel || selectedOption?.label || placeholder}
        onClick={() => setOpen(prev => !prev)}
        className="flex min-h-11 w-full cursor-pointer items-center justify-between gap-2 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-left text-sm font-medium transition-colors hover:border-[var(--color-muted)] focus-visible:border-[var(--color-primary)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 focus-visible:outline-solid active:scale-[0.99]"
      >
        <span className="flex min-w-0 items-center gap-2 truncate">
          {selectedOption?.icon}
          <span className={selectedOption ? 'text-[var(--color-text)]' : 'text-[var(--color-muted)]'}>
            {selectedOption ? selectedOption.label : placeholder || 'Chọn...'}
          </span>
        </span>
        <ChevronDown
          size={16}
          className={`shrink-0 text-[var(--color-muted)] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div
          id={listboxId}
          role="listbox"
          className="absolute left-0 top-full z-40 mt-1 max-h-60 w-full min-w-[12rem] overflow-auto rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] p-1 shadow-lg animate-in fade-in zoom-in-95 duration-100"
        >
          {searchable && (
            <div className="sticky top-0 z-10 border-b border-[var(--color-border)] bg-[var(--color-surface)] p-1.5">
              <div className="relative">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-muted)]" />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder={searchPlaceholder}
                  className="min-h-9 w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] py-1 pl-8 pr-2 text-xs text-[var(--color-text)] placeholder:text-[var(--color-muted)] focus-visible:border-[var(--color-primary)] focus-visible:outline-none"
                />
              </div>
            </div>
          )}

          <div className="py-1">
            {filteredOptions.length === 0 ? (
              <div className="p-3 text-center text-xs text-[var(--color-muted)]">
                Không tìm thấy kết quả
              </div>
            ) : (
              filteredOptions.map(option => {
                const isSelected = option.value === value
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => select(option.value)}
                    className={`flex min-h-10 w-full cursor-pointer items-center justify-between gap-2 rounded px-2.5 py-2 text-left text-sm transition-colors ${
                      isSelected
                        ? 'bg-[var(--color-primary-soft)] font-semibold text-[var(--color-primary)]'
                        : 'text-[var(--color-text)] hover:bg-[var(--color-surface-soft)]'
                    }`}
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      {option.icon}
                      <span className="truncate">{option.label}</span>
                      {option.description && (
                        <span className="text-xs text-[var(--color-muted)] font-normal">
                          · {option.description}
                        </span>
                      )}
                    </div>
                    {isSelected && <Check size={16} className="shrink-0 text-[var(--color-primary)]" />}
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}

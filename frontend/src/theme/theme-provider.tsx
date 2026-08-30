import { createContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

export type Theme = 'light' | 'dark'
export const ThemeContext = createContext<{ theme: Theme; toggleTheme: () => void } | null>(null)
const storageKey = 'all-voice-theme'

function getInitialTheme(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)
  useEffect(() => { document.documentElement.classList.toggle('dark', theme === 'dark'); localStorage.setItem(storageKey, theme) }, [theme])
  const value = useMemo(() => ({ theme, toggleTheme: () => setTheme(value => value === 'dark' ? 'light' : 'dark') }), [theme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

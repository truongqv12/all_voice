import { Moon, Sun } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { IconButton } from './icon-button'
import { useTheme } from '../../theme/use-theme'

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const { t } = useTranslation()
  const isDark = theme === 'dark'
  return <IconButton onClick={toggleTheme} aria-label={isDark ? t('theme.light') : t('theme.dark')}>{isDark ? <Sun size={20} /> : <Moon size={20} />}</IconButton>
}

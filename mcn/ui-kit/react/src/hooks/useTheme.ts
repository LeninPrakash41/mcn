import { useState, useEffect, useCallback } from 'react'

export type Theme = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'mcn-theme'

function getSystemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  const resolved = theme === 'system' ? getSystemTheme() : theme
  document.documentElement.classList.remove('light', 'dark')
  document.documentElement.classList.add(resolved)
  document.documentElement.setAttribute('data-theme', resolved)
}

/**
 * Hook for managing dark/light/system theme.
 * Persists to localStorage and applies the `dark` / `light` class to <html>.
 *
 * @example
 * const { theme, resolvedTheme, setTheme, toggle } = useTheme()
 * // resolvedTheme is always 'light' | 'dark' (never 'system')
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => {
    try {
      return (localStorage.getItem(STORAGE_KEY) as Theme) ?? 'light'
    } catch {
      return 'light'
    }
  })

  const resolvedTheme: 'light' | 'dark' = theme === 'system' ? getSystemTheme() : theme

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  // Listen for system theme changes when mode is 'system'
  useEffect(() => {
    if (theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => applyTheme('system')
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme])

  const setTheme = useCallback((next: Theme) => {
    try { localStorage.setItem(STORAGE_KEY, next) } catch {}
    setThemeState(next)
  }, [])

  const toggle = useCallback(() => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')
  }, [resolvedTheme, setTheme])

  return { theme, resolvedTheme, setTheme, toggle }
}

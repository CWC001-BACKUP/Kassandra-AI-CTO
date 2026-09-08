import { createContext, useContext, type CSSProperties, type ReactNode } from 'react'
import { colors, colorsToCssVars, type ThemeColors } from './colors'

const ThemeContext = createContext<ThemeColors>(colors)

interface ThemeProviderProps {
  children: ReactNode
  /** Override palette — defaults to logo-derived colors */
  palette?: Partial<ThemeColors>
}

export function ThemeProvider({ children, palette }: ThemeProviderProps) {
  const merged = { ...colors, ...palette }
  const cssVars = colorsToCssVars(merged)

  return (
    <ThemeContext.Provider value={merged}>
      <div style={cssVars as CSSProperties} className="min-h-screen">
        {children}
      </div>
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}

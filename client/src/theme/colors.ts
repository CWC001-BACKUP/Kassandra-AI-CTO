/**
 * Kassandra design tokens — single source of truth for the visual system.
 */
export const colors = {
  background: '#030712',
  backgroundAlt: '#0a0f1e',
  surface: '#0c1222',
  surfaceElevated: '#111827',
  surfaceHover: '#1a2235',
  surfaceGlass: 'rgba(12, 18, 34, 0.72)',

  border: '#1e293b',
  borderSubtle: 'rgba(30, 41, 59, 0.6)',
  borderGlow: 'rgba(0, 210, 255, 0.25)',

  cyan: '#00D2FF',
  cyanLight: '#33CCFF',
  cyanBright: '#00E5FF',
  cyanMuted: 'rgba(0, 210, 255, 0.12)',

  purple: '#A020F0',
  magenta: '#FF00FF',
  purpleDeep: '#7D26CD',
  purpleMuted: 'rgba(160, 32, 240, 0.12)',

  blue: '#0072FF',
  blueDeep: '#0055FF',

  highlight: '#E0F7FF',
  text: '#F8FAFC',
  textMuted: '#94a3b8',
  textDim: '#64748b',

  success: '#10b981',
  warning: '#f59e0b',
  error: '#ef4444',
} as const

export type ThemeColors = typeof colors

export function colorsToCssVars(c: ThemeColors): Record<string, string> {
  return {
    '--color-bg': c.background,
    '--color-bg-alt': c.backgroundAlt,
    '--color-surface': c.surface,
    '--color-surface-elevated': c.surfaceElevated,
    '--color-surface-hover': c.surfaceHover,
    '--color-surface-glass': c.surfaceGlass,
    '--color-border': c.border,
    '--color-border-subtle': c.borderSubtle,
    '--color-border-glow': c.borderGlow,
    '--color-cyan': c.cyan,
    '--color-cyan-light': c.cyanLight,
    '--color-cyan-bright': c.cyanBright,
    '--color-cyan-muted': c.cyanMuted,
    '--color-purple': c.purple,
    '--color-magenta': c.magenta,
    '--color-purple-deep': c.purpleDeep,
    '--color-purple-muted': c.purpleMuted,
    '--color-blue': c.blue,
    '--color-blue-deep': c.blueDeep,
    '--color-highlight': c.highlight,
    '--color-text': c.text,
    '--color-text-muted': c.textMuted,
    '--color-text-dim': c.textDim,
    '--color-success': c.success,
    '--color-warning': c.warning,
    '--color-error': c.error,
    '--gradient-primary': `linear-gradient(135deg, ${c.cyan} 0%, ${c.blue} 50%, ${c.purple} 100%)`,
    '--gradient-accent': `linear-gradient(135deg, ${c.cyanBright} 0%, ${c.magenta} 100%)`,
    '--gradient-surface': `linear-gradient(180deg, ${c.surfaceElevated} 0%, ${c.surface} 100%)`,
    '--gradient-hero': `radial-gradient(ellipse 80% 60% at 50% -20%, rgba(0, 210, 255, 0.15), transparent), radial-gradient(ellipse 60% 50% at 80% 50%, rgba(160, 32, 240, 0.1), transparent)`,
    '--shadow-glow-cyan': `0 0 24px rgba(0, 210, 255, 0.25), 0 0 48px rgba(0, 210, 255, 0.1)`,
    '--shadow-glow-purple': `0 0 24px rgba(160, 32, 240, 0.25), 0 0 48px rgba(160, 32, 240, 0.1)`,
    '--shadow-card': `0 4px 24px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.03)`,
    '--shadow-elevated': `0 8px 32px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.05)`,
    '--radius-sm': '0.5rem',
    '--radius-md': '0.75rem',
    '--radius-lg': '1rem',
    '--radius-xl': '1.25rem',
    '--transition-fast': '150ms',
    '--transition-base': '250ms',
    '--transition-slow': '400ms',
  }
}

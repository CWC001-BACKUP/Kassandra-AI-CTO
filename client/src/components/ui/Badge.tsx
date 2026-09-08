import { type ReactNode } from 'react'

type BadgeVariant = 'default' | 'cyan' | 'purple' | 'success' | 'warning'

interface BadgeProps {
  children: ReactNode
  variant?: BadgeVariant
  dot?: boolean
  className?: string
}

const variants: Record<BadgeVariant, string> = {
  default: 'bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] border-[var(--color-border)]',
  cyan: 'bg-[var(--color-cyan-muted)] text-[var(--color-cyan)] border-[var(--color-cyan)]/20',
  purple: 'bg-[var(--color-purple-muted)] text-[var(--color-purple)] border-[var(--color-purple)]/20',
  success: 'bg-[var(--color-success)]/10 text-[var(--color-success)] border-[var(--color-success)]/20',
  warning: 'bg-[var(--color-warning)]/10 text-[var(--color-warning)] border-[var(--color-warning)]/20',
}

export function Badge({ children, variant = 'default', dot, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium tracking-wide ${variants[variant]} ${className}`}
    >
      {dot && (
        <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse-glow" />
      )}
      {children}
    </span>
  )
}

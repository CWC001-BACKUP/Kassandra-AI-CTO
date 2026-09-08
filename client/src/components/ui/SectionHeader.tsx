import { type ReactNode } from 'react'
import { Badge } from './Badge'

interface SectionHeaderProps {
  badge?: string
  title: string
  description?: string
  align?: 'left' | 'center'
  className?: string
  children?: ReactNode
}

export function SectionHeader({
  badge,
  title,
  description,
  align = 'center',
  className = '',
}: SectionHeaderProps) {
  const alignClass = align === 'center' ? 'text-center mx-auto' : ''

  return (
    <div className={`max-w-3xl ${alignClass} ${className}`}>
      {badge && (
        <div className={`mb-4 ${align === 'center' ? 'flex justify-center' : ''}`}>
          <Badge variant="cyan">{badge}</Badge>
        </div>
      )}
      <h2 className="font-display text-3xl font-bold tracking-tight lg:text-4xl">
        {title}
      </h2>
      {description && (
        <p className="mt-4 text-base leading-relaxed text-[var(--color-text-muted)]">
          {description}
        </p>
      )}
    </div>
  )
}

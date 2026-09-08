import { type ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  glow?: boolean
  interactive?: boolean
  padding?: boolean
}

export function Card({
  children,
  className = '',
  glow,
  interactive,
  padding = false,
}: CardProps) {
  return (
    <div
      className={[
        'glass-card',
        glow ? 'glass-card-glow' : '',
        interactive ? 'glass-card-interactive glow-border' : '',
        padding ? 'p-6' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {children}
    </div>
  )
}

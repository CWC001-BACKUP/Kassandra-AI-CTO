import { type ReactNode } from 'react'

interface GradientTextProps {
  children: ReactNode
  as?: 'span' | 'h1' | 'h2' | 'h3' | 'p'
  className?: string
}

export function GradientText({ children, as: Tag = 'span', className = '' }: GradientTextProps) {
  return (
    <Tag className={`gradient-text ${className}`}>
      {children}
    </Tag>
  )
}

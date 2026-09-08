import { Spinner } from './Spinner'

interface LoadingStateProps {
  message?: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

export function LoadingState({
  message = 'Loading…',
  className = '',
  size = 'md',
}: LoadingStateProps) {
  return (
    <div
      className={`flex items-center gap-3 text-sm text-[var(--color-text-muted)] ${className}`}
    >
      <Spinner size={size === 'lg' ? 'lg' : size === 'sm' ? 'sm' : 'md'} />
      <span>{message}</span>
    </div>
  )
}

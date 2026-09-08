import { type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Spinner } from './Spinner'
import { buttonClasses, type ButtonSize, type ButtonVariant } from './buttonStyles'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  children: ReactNode
  fullWidth?: boolean
  loading?: boolean
  loadingText?: string
}

export function Button({
  variant = 'primary',
  size = 'md',
  fullWidth,
  className = '',
  children,
  loading = false,
  loadingText,
  disabled,
  ...props
}: ButtonProps) {
  const spinnerSize = size === 'lg' ? 'sm' : 'xs'

  return (
    <button
      className={`${buttonClasses(variant, size, className)} ${fullWidth ? 'w-full' : ''}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Spinner size={spinnerSize} />}
      <span className="truncate">{loading && loadingText ? loadingText : children}</span>
    </button>
  )
}

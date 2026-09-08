export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger' | 'link'
export type ButtonSize = 'sm' | 'md' | 'lg'

/** Sharp-edged glass panel with a subtle 3D lift — shared by all buttons. */
export const buttonBase =
  'inline-flex items-center justify-center gap-2 font-medium whitespace-nowrap rounded-none border ' +
  'backdrop-blur-md transition-all duration-200 select-none ' +
  'shadow-[inset_0_1px_0_rgba(255,255,255,0.14),inset_0_-1px_0_rgba(0,0,0,0.25),0_6px_20px_rgba(0,0,0,0.35)] ' +
  'hover:-translate-y-px hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.18),inset_0_-1px_0_rgba(0,0,0,0.2),0_10px_28px_rgba(0,0,0,0.45)] ' +
  'active:translate-y-px active:brightness-95 ' +
  'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 disabled:active:translate-y-0'

export const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    'border-[var(--color-cyan)]/50 bg-gradient-to-b from-[rgba(0,210,255,0.35)] via-[rgba(59,130,246,0.28)] to-[rgba(124,58,237,0.22)] ' +
    'text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.22),inset_0_-2px_0_rgba(0,0,0,0.3),0_0_24px_rgba(0,210,255,0.25)] ' +
    'hover:border-[var(--color-cyan)]/70 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.28),0_0_32px_rgba(160,32,240,0.2)]',
  secondary:
    'border-[var(--color-purple)]/40 bg-[rgba(18,24,42,0.72)] text-[var(--color-highlight)] ' +
    'hover:border-[var(--color-purple)]/60 hover:bg-[rgba(24,32,56,0.85)]',
  ghost:
    'border-transparent bg-[rgba(12,18,34,0.45)] text-[var(--color-text-muted)] shadow-none ' +
    'hover:border-[var(--color-cyan)]/25 hover:bg-[rgba(0,210,255,0.08)] hover:text-[var(--color-cyan)] ' +
    'hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_4px_16px_rgba(0,0,0,0.3)]',
  outline:
    'border-[var(--color-border)] bg-[rgba(10,16,30,0.55)] text-[var(--color-text)] ' +
    'hover:border-[var(--color-cyan)]/45 hover:bg-[rgba(0,210,255,0.06)] hover:text-[var(--color-cyan)]',
  danger:
    'border-[var(--color-error)]/45 bg-[rgba(40,12,18,0.55)] text-[var(--color-error)] ' +
    'hover:border-[var(--color-error)]/65 hover:bg-[rgba(60,16,24,0.65)]',
  link:
    'min-h-0 min-w-0 border-transparent bg-transparent px-0 py-0 text-[var(--color-cyan)] shadow-none ' +
    'hover:translate-y-0 hover:bg-transparent hover:underline active:translate-y-0',
}

export const buttonSizes: Record<ButtonSize, string> = {
  sm: 'min-h-[2.375rem] min-w-[5rem] px-4 py-2 text-xs tracking-wide',
  md: 'min-h-[2.75rem] min-w-[5.75rem] px-5 py-2.5 text-sm',
  lg: 'min-h-[3.25rem] min-w-[7rem] px-7 py-3.5 text-base',
}

export function buttonClasses(
  variant: ButtonVariant = 'primary',
  size: ButtonSize = 'md',
  extra = '',
): string {
  if (variant === 'link') {
    return [buttonVariants.link, extra].filter(Boolean).join(' ')
  }
  const sizeClasses = buttonSizes[size]
  return [buttonBase, buttonVariants[variant], sizeClasses, extra].filter(Boolean).join(' ')
}

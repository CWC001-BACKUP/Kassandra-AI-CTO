/** Shared sharp glass surface classes — cards, fields, sidebars. */

export const glassFieldClass =
  'glass-field w-full px-4 py-3 text-sm text-[var(--color-text)] ' +
  'placeholder:text-[var(--color-text-dim)] transition-all duration-200 ' +
  'disabled:cursor-not-allowed disabled:opacity-60'

export const glassFieldErrorClass =
  'border-[var(--color-error)] focus:border-[var(--color-error)] focus:ring-[var(--color-error)]/20'

export const glassFieldDefaultClass =
  'border-[var(--color-border-subtle)] hover:border-[var(--color-border)] ' +
  'focus:border-[var(--color-cyan)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--color-cyan)]/20'

import { Spinner } from './Spinner'

export function ChatTypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] glass-panel border border-[var(--color-border-subtle)] px-5 py-4">
        <div className="flex items-center gap-3 text-sm text-[var(--color-text-muted)]">
          <Spinner size="sm" />
          <span>Kassandra is thinking…</span>
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { glassFieldClass, glassFieldDefaultClass } from '../../components/ui/surfaceStyles'
import { Card } from '../../components/ui/Card'
import { PageHeader } from '../../components/ui/PageHeader'
import { LoadingState } from '../../components/ui/LoadingState'
import { logsApi } from '../../services/api'

type LogLevel = 'all' | 'info' | 'warn' | 'error'

const levelColors: Record<string, string> = {
  info: 'text-[var(--color-cyan)] bg-[var(--color-cyan)]/10',
  warn: 'text-[var(--color-warning)] bg-[var(--color-warning)]/10',
  error: 'text-[var(--color-error)] bg-[var(--color-error)]/10',
}

function formatTimestamp(iso: string) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export function LogsPage() {
  const [filter, setFilter] = useState<LogLevel>('all')
  const [search, setSearch] = useState('')

  const { data: logs = [], isLoading, isError } = useQuery({
    queryKey: ['logs', filter, search],
    queryFn: () =>
      logsApi.list({
        level: filter === 'all' ? undefined : filter,
        search: search || undefined,
      }),
  })

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader
        title="Logs"
        description="Activity from repo analysis, webhooks, reports, and chat"
      />

      <div className="mb-6 flex flex-wrap items-center gap-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search logs…"
          className={`${glassFieldClass} ${glassFieldDefaultClass}`}
        />
        <div className="flex gap-1 border border-[var(--color-border)] p-1">
          {(['all', 'info', 'warn', 'error'] as LogLevel[]).map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => setFilter(level)}
              className={`btn-glass btn-glass-sm capitalize ${
                filter === level ? 'btn-glass-filter-active' : 'btn-glass-filter-inactive'
              }`}
            >
              {level}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <LoadingState message="Loading activity logs…" className="mb-6" />}
      {isError && (
        <Card className="p-6 text-sm text-[var(--color-error)]">
          Could not load logs.
        </Card>
      )}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-xs uppercase tracking-wider text-[var(--color-text-dim)]">
                <th className="px-4 py-3 font-medium">Level</th>
                <th className="px-4 py-3 font-medium">Timestamp</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {logs.length === 0 && !isLoading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-[var(--color-text-muted)]">
                    No logs yet. Add a project and run analysis to get started.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr
                    key={log.id}
                    className="transition-colors hover:bg-[var(--color-surface-hover)]"
                  >
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded px-2 py-0.5 text-xs font-medium uppercase ${levelColors[log.level] ?? levelColors.info}`}
                      >
                        {log.level}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-[var(--color-text-dim)]">
                      {formatTimestamp(log.timestamp)}
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">
                      {log.source}
                    </td>
                    <td className="px-4 py-3">{log.message}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

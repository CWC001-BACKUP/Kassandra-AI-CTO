import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Card } from '../../components/ui/Card'
import { PageHeader } from '../../components/ui/PageHeader'
import { FeatureIcon } from '../../components/ui/FeatureIcon'
import { Spinner } from '../../components/ui/Spinner'
import { apiFetch, dashboardApi } from '../../services/api'
import type { HealthResponse } from '../../types'
import type { IconName } from '../../components/ui/FeatureIcon'

const quickActions = [
  { to: '/dashboard/chat', label: 'Ask AI CTO', desc: 'Get engineering insights', icon: 'chat' as const },
  { to: '/dashboard/teach', label: 'Teach Kassandra', desc: 'Fill institutional gaps', icon: 'reports' as const },
  { to: '/dashboard/changes', label: 'View Changes', desc: 'Recent PRs & commits', icon: 'changes' as const },
  { to: '/dashboard/reports', label: 'Generate Report', desc: 'Sprint summary', icon: 'reports' as const },
]

const activityColors: Record<string, string> = {
  commit: 'from-[var(--color-cyan)] to-[var(--color-blue)]',
  decision: 'from-[var(--color-purple)] to-[var(--color-magenta)]',
  pr: 'from-[var(--color-blue)] to-[var(--color-cyan)]',
  incident: 'from-[var(--color-warning)] to-[var(--color-error)]',
  analysis: 'from-[var(--color-purple)] to-[var(--color-cyan)]',
  webhook: 'from-[var(--color-cyan)] to-[var(--color-blue)]',
  reports: 'from-[var(--color-magenta)] to-[var(--color-purple)]',
  memory: 'from-[var(--color-purple)] to-[var(--color-magenta)]',
  system: 'from-[var(--color-cyan)] to-[var(--color-blue)]',
}

function relativeTime(iso: string) {
  try {
    const delta = Date.now() - new Date(iso).getTime()
    const hours = Math.floor(delta / 3600000)
    if (hours < 1) return 'just now'
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  } catch {
    return ''
  }
}

export function DashboardHomePage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<HealthResponse>('/health'),
  })

  const statsQuery = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: dashboardApi.stats,
  })

  const activityQuery = useQuery({
    queryKey: ['dashboard-activity'],
    queryFn: dashboardApi.activity,
  })

  const stats = statsQuery.data

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader
        title="Dashboard"
        description="Welcome back. Here's what's happening with your projects."
      />

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-dim)]">
            API Status
          </p>
          <p className="mt-2 font-display text-lg font-semibold">
            {isLoading && (
              <span className="inline-flex items-center gap-2 text-[var(--color-text-muted)]">
                <Spinner size="sm" />
                Checking…
              </span>
            )}
            {isError && (
              <span className="text-[var(--color-error)]">Disconnected</span>
            )}
            {data && (
              <span className="flex items-center gap-2 text-[var(--color-success)]">
                <span className="h-2 w-2 rounded-full bg-[var(--color-success)] animate-pulse-glow" />
                {data.status}
              </span>
            )}
          </p>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-dim)]">
            Projects
          </p>
          <p className="mt-2 font-display text-lg font-semibold">
            {stats?.projects_count ?? 0} connected
          </p>
          {stats?.active_project && (
            <p className="mt-1 truncate text-xs text-[var(--color-text-dim)]">
              Active: {stats.active_project}
            </p>
          )}
        </Card>
        <Card className="p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-dim)]">
            Memories
          </p>
          <p className="mt-2 font-display text-lg font-semibold gradient-text">
            {stats?.memory_count ?? 0} stored
          </p>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-dim)]">
            Recent Changes
          </p>
          <p className="mt-2 font-display text-lg font-semibold">
            {stats?.changes_today ?? 0} tracked
          </p>
        </Card>
      </div>

      <div className="grid gap-10 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <h2 className="mb-5 font-display text-sm font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
            Quick Actions
          </h2>
          <div className="space-y-4">
            {quickActions.map((action) => (
              <Link key={action.to} to={action.to} className="block">
                <Card interactive className="flex items-center gap-5 p-5">
                  <div className={`glass-icon-tile flex h-11 w-11 shrink-0 items-center justify-center bg-gradient-to-br ${activityColors[action.icon] ?? 'from-[var(--color-cyan)] to-[var(--color-blue)]'}`}>
                    <FeatureIcon name={action.icon} className="!h-5 !w-5" />
                  </div>
                  <div className="min-w-0 py-0.5">
                    <p className="text-sm font-medium leading-snug">{action.label}</p>
                    <p className="mt-1.5 text-xs leading-relaxed text-[var(--color-text-dim)]">{action.desc}</p>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2">
          <h2 className="mb-5 font-display text-sm font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
            Recent Activity
          </h2>
          <Card>
            <div className="divide-y divide-[var(--color-border-subtle)]">
              {(activityQuery.data ?? []).length === 0 ? (
                <p className="p-8 text-sm leading-relaxed text-[var(--color-text-muted)]">
                  No activity yet. Add a project and run analysis to populate logs.
                </p>
              ) : (
                activityQuery.data?.map((item, i) => (
                  <div key={i} className="flex items-start gap-5 p-5 transition-colors hover:bg-[var(--color-surface-hover)]/40">
                    <div className={`glass-icon-tile flex h-10 w-10 shrink-0 items-center justify-center bg-gradient-to-br ${activityColors[item.type] ?? activityColors.system}`}>
                      <FeatureIcon name={(item.type === 'webhook' ? 'commit' : item.type) as IconName} className="!h-4 !w-4" />
                    </div>
                    <div className="min-w-0 flex-1 py-0.5">
                      <p className="text-sm leading-relaxed">{item.message}</p>
                      <p className="mt-2 text-xs text-[var(--color-text-dim)]">
                        {relativeTime(item.time)}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

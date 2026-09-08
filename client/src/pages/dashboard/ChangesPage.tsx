import { useQuery } from '@tanstack/react-query'
import { Card } from '../../components/ui/Card'
import { PageHeader } from '../../components/ui/PageHeader'
import { FeatureIcon } from '../../components/ui/FeatureIcon'
import { LoadingState } from '../../components/ui/LoadingState'
import { changesApi } from '../../services/api'

const statusStyles: Record<string, string> = {
  merged: 'text-[var(--color-purple)] bg-[var(--color-purple)]/10',
  open: 'text-[var(--color-cyan)] bg-[var(--color-cyan)]/10',
  committed: 'text-[var(--color-success)] bg-[var(--color-success)]/10',
}

export function ChangesPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['changes'],
    queryFn: () => changesApi.list(),
  })

  const changes = data?.changes ?? []
  const stats = data?.stats ?? {
    this_week: 0,
    open_prs: 0,
    total_additions: 0,
    total_deletions: 0,
  }

  return (
    <div className="min-w-0 overflow-x-hidden p-4 sm:p-6 lg:p-8">
      <PageHeader
        title="Changes"
        description={
          data?.repo_full_name
            ? `Pull requests and commits from ${data.repo_full_name}`
            : 'Track pull requests and commits for your active project'
        }
      />

      {!data?.repo_full_name && !isLoading && (
        <Card className="mb-6 p-6 text-sm text-[var(--color-text-muted)]">
          No active project. Add a repository under Projects and set it as active.
        </Card>
      )}

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <p className="text-xs uppercase tracking-wider text-[var(--color-text-dim)]">
            Recent
          </p>
          <p className="mt-1 text-2xl font-bold">{stats.this_week}</p>
          <p className="text-xs text-[var(--color-text-dim)]">changes tracked</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs uppercase tracking-wider text-[var(--color-text-dim)]">
            Open PRs
          </p>
          <p className="mt-1 text-2xl font-bold">{stats.open_prs}</p>
          <p className="text-xs text-[var(--color-text-dim)]">awaiting review</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs uppercase tracking-wider text-[var(--color-text-dim)]">
            Lines Changed
          </p>
          <p className="mt-1 text-2xl font-bold">
            <span className="text-[var(--color-success)]">+{stats.total_additions}</span>
            {' / '}
            <span className="text-[var(--color-error)]">-{stats.total_deletions}</span>
          </p>
        </Card>
      </div>

      {isLoading && (
        <LoadingState message="Loading changes from GitHub…" className="mb-6" />
      )}
      {isError && (
        <Card className="p-6 text-sm text-[var(--color-error)]">
          Could not load changes. Re-connect GitHub if your token expired.
        </Card>
      )}

      <div className="space-y-3">
        {changes.map((change) => (
          <Card key={`${change.type}-${change.id}`} interactive className="overflow-hidden p-5">
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--color-cyan)] to-[var(--color-blue)]">
                <FeatureIcon
                  name={change.type === 'pr' ? 'pr' : 'commit'}
                  className="!h-4 !w-4"
                />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  {change.html_url ? (
                    <a
                      href={change.html_url}
                      target="_blank"
                      rel="noreferrer"
                      className="min-w-0 break-words text-sm font-medium hover:text-[var(--color-cyan)]"
                    >
                      {change.title}
                    </a>
                  ) : (
                    <h3 className="min-w-0 break-words text-sm font-medium">{change.title}</h3>
                  )}
                  <span
                    className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium capitalize ${statusStyles[change.status] ?? statusStyles.committed}`}
                  >
                    {change.status}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--color-text-dim)]">
                  <span className="max-w-full truncate">{change.author}</span>
                  <span className="max-w-full truncate">{change.branch}</span>
                  {change.files > 0 && <span>{change.files} files</span>}
                  {change.additions > 0 && (
                    <span className="text-[var(--color-success)]">+{change.additions}</span>
                  )}
                  {change.deletions > 0 && (
                    <span className="text-[var(--color-error)]">-{change.deletions}</span>
                  )}
                  <span className="shrink-0">{change.time}</span>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

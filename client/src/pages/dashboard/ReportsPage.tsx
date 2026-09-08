import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { PageHeader } from '../../components/ui/PageHeader'
import { reportsApi } from '../../services/api'
import type { GenerateReportRequest, Report } from '../../types'

const reportTypes = [
  {
    id: 'sprint' as const,
    title: 'Sprint Summary',
    description: 'Overview of changes, decisions, and blockers from the current sprint.',
    icon: '🏃',
  },
  {
    id: 'incident' as const,
    title: 'Incident Report',
    description: 'Post-mortem template with timeline, root cause, and action items.',
    icon: '🔥',
  },
  {
    id: 'architecture' as const,
    title: 'Architecture Review',
    description: 'Current system design, recent decisions, and technical debt assessment.',
    icon: '🏗️',
  },
  {
    id: 'onboarding' as const,
    title: 'Onboarding Brief',
    description: 'Everything a new team member needs to know about the project.',
    icon: '👋',
  },
]

export function ReportsPage() {
  const [selected, setSelected] = useState<GenerateReportRequest['report_type'] | null>(null)
  const [viewing, setViewing] = useState<Report | null>(null)
  const queryClient = useQueryClient()

  const reportsQuery = useQuery({
    queryKey: ['reports'],
    queryFn: reportsApi.list,
  })

  const generateMutation = useMutation({
    mutationFn: (reportType: GenerateReportRequest['report_type']) =>
      reportsApi.generate({ report_type: reportType }),
    onSuccess: (report) => {
      setViewing(report)
      void queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })

  const handleGenerate = () => {
    if (!selected) return
    generateMutation.mutate(selected)
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader
        title="Reports"
        description="Generate engineering reports from project memory and GitHub changes"
      />

      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
        Generate New Report
      </h2>
      <div className="mb-10 grid gap-4 sm:grid-cols-2">
        {reportTypes.map((report) => (
          <button
            key={report.id}
            type="button"
            onClick={() => setSelected(report.id)}
            className="block w-full rounded-none text-left"
          >
            <Card
              className={`p-5 transition-all ${
                selected === report.id
                  ? 'border-[var(--color-cyan)]/50 shadow-[var(--shadow-glow-cyan)]'
                  : 'hover:border-[var(--color-cyan)]/20'
              }`}
            >
              <div className="flex items-start gap-4">
                <span className="text-2xl">{report.icon}</span>
                <div>
                  <h3 className="font-medium">{report.title}</h3>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    {report.description}
                  </p>
                </div>
              </div>
            </Card>
          </button>
        ))}
      </div>

      {selected && (
        <div className="mb-10">
          <Button
            onClick={handleGenerate}
            loading={generateMutation.isPending}
            loadingText="Generating…"
            disabled={!selected}
          >
            Generate Report
          </Button>
          {generateMutation.isPending && (
            <p className="mt-2 text-sm text-[var(--color-text-muted)]">
              Analyzing project memory and recent changes…
            </p>
          )}
        </div>
      )}

      {viewing && (
        <Card className="mb-10 p-6">
          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 className="text-lg font-semibold">{viewing.title}</h2>
            <Button variant="ghost" size="sm" onClick={() => setViewing(null)}>
              Close
            </Button>
          </div>
          <div className="prose prose-invert max-w-none whitespace-pre-wrap text-sm text-[var(--color-text-muted)]">
            {viewing.content}
          </div>
        </Card>
      )}

      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
        Recent Reports
      </h2>
      <Card>
        <div className="divide-y divide-[var(--color-border)]">
          {(reportsQuery.data ?? []).length === 0 ? (
            <p className="p-6 text-sm text-[var(--color-text-muted)]">
              No reports yet. Select a type above and generate your first report.
            </p>
          ) : (
            reportsQuery.data?.map((report) => (
              <div
                key={report.id}
                className="flex items-center justify-between p-4 transition-colors hover:bg-[var(--color-surface-hover)]"
              >
                <div className="flex items-center gap-4">
                  <span className="text-lg">
                    {reportTypes.find((t) => t.id === report.report_type)?.icon}
                  </span>
                  <div>
                    <p className="text-sm font-medium">{report.title}</p>
                    <p className="text-xs text-[var(--color-text-dim)]">
                      {new Date(report.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      report.status === 'ready'
                        ? 'text-[var(--color-success)] bg-[var(--color-success)]/10'
                        : report.status === 'failed'
                          ? 'text-[var(--color-error)] bg-[var(--color-error)]/10'
                          : 'text-[var(--color-cyan)] bg-[var(--color-cyan)]/10'
                    }`}
                  >
                    {report.status}
                  </span>
                  <Button variant="ghost" size="sm" onClick={() => setViewing(report)}>
                    View
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  )
}

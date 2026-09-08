import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { LoadingState } from '../../components/ui/LoadingState'
import { PageHeader } from '../../components/ui/PageHeader'
import { glassFieldClass, glassFieldDefaultClass } from '../../components/ui/surfaceStyles'
import { projectsApi } from '../../services/api'
import type { ProjectUnderstanding } from '../../types'

function ConfidenceBadge({ value }: { value?: string | null }) {
  const v = (value || '').toLowerCase()
  if (v === 'confirmed' || v === 'high') return <Badge variant="success">{value}</Badge>
  if (v === 'inferred' || v === 'medium') return <Badge variant="warning">{value}</Badge>
  if (v === 'observed') return <Badge variant="cyan">{value}</Badge>
  return <Badge>{value || 'unknown'}</Badge>
}

function UnderstandingSummary({ data }: { data: ProjectUnderstanding }) {
  return (
    <div className="space-y-6">
      <Card className="p-5">
        <p className="whitespace-pre-wrap text-sm text-[var(--color-text-muted)]">
          {data.interview_intro}
        </p>
        <p className="mt-4 text-sm font-medium text-[var(--color-cyan)]">{data.headline}</p>
        <div className="mt-4 flex flex-wrap gap-2 text-xs text-[var(--color-text-dim)]">
          <span>{data.counts.observed ?? 0} observed</span>
          <span>·</span>
          <span>{data.counts.inferred ?? 0} inferred</span>
          <span>·</span>
          <span>{data.counts.confirmed ?? 0} confirmed</span>
          <span>·</span>
          <span>{data.counts.knowledge_gaps ?? 0} gaps</span>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
            Architecture
          </h3>
          {data.architecture.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--color-text-muted)]">
              No architecture observations yet. Run Analyze on the project.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {data.architecture.map((item, idx) => (
                <li
                  key={`${item.title}-${idx}`}
                  className="flex items-start justify-between gap-3 text-sm"
                >
                  <span>{item.title}</span>
                  <ConfidenceBadge value={item.confidence} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
            Historical evolution
          </h3>
          {data.historical_evolution.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--color-text-muted)]">
              No meaningful historical signals stored yet.
            </p>
          ) : (
            <ul className="mt-3 space-y-3">
              {data.historical_evolution.slice(0, 8).map((item, idx) => (
                <li key={`${item.title}-${idx}`} className="text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{item.title}</span>
                    <ConfidenceBadge value={item.confidence} />
                  </div>
                  {item.reason && (
                    <p className="mt-1 text-[var(--color-text-muted)]">{item.reason}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

type GapItem = ProjectUnderstanding['knowledge_gaps'][number]

export function TeachPage() {
  const queryClient = useQueryClient()
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [extras, setExtras] = useState<Record<string, string>>({})
  const [freeform, setFreeform] = useState('')
  const [status, setStatus] = useState<string | null>(null)

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
  })

  const activeProject = useMemo(
    () => (projectsQuery.data ?? []).find((p) => p.is_active) ?? (projectsQuery.data ?? [])[0],
    [projectsQuery.data],
  )

  const understandingQuery = useQuery({
    queryKey: ['project-understanding', activeProject?.id],
    queryFn: () => projectsApi.understanding(activeProject!.id),
    enabled: Boolean(activeProject?.id),
  })

  const gaps = understandingQuery.data?.knowledge_gaps ?? []

  const gapKey = (gap: GapItem, index: number) =>
    gap.memory_id || `${gap.question}-${index}`

  useEffect(() => {
    if (!gaps.length) {
      setSelectedKey(null)
      return
    }
    const keys = gaps.map((g, i) => gapKey(g, i))
    if (!selectedKey || !keys.includes(selectedKey)) {
      setSelectedKey(keys[0])
    }
  }, [gaps, selectedKey])

  const selectedGap = useMemo(() => {
    if (!selectedKey) return null
    return gaps.find((g, i) => gapKey(g, i) === selectedKey) ?? null
  }, [gaps, selectedKey])

  const teachMutation = useMutation({
    mutationFn: (payload: {
      text: string
      gap_memory_id?: string | null
      question?: string | null
      extra?: string | null
      mode: 'gap' | 'extra'
    }) =>
      projectsApi.teach(activeProject!.id, payload.text, {
        gap_memory_id: payload.gap_memory_id,
        question: payload.question,
        extra: payload.extra,
      }),
    onSuccess: (result, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['project-understanding'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })

      if (result.stored || result.gap_resolved) {
        const title =
          typeof result.memory?.title === 'string'
            ? result.memory.title
            : variables.question || 'memory'
        const resolved = result.gap_resolved
          ? ' Gap closed.'
          : ''
        setStatus(`Saved to Sibyl: ${title} (confirmed).${resolved}`)
        if (variables.mode === 'gap' && variables.question) {
          setAnswers((prev) => {
            const next = { ...prev }
            // clear by finding keys that match question text in gap list after refresh
            for (const key of Object.keys(next)) {
              if (key.includes(variables.question!.slice(0, 24))) delete next[key]
            }
            if (selectedKey) delete next[selectedKey]
            return next
          })
          setExtras((prev) => {
            const next = { ...prev }
            if (selectedKey) delete next[selectedKey]
            return next
          })
        } else {
          setFreeform('')
        }
      } else if (result.duplicate) {
        setStatus(
          result.gap_resolved
            ? 'Similar memory already in Sibyl — gap closed.'
            : 'Similar memory already exists in Sibyl — not duplicated.',
        )
      } else {
        setStatus(result.reason || 'Nothing stored.')
      }
    },
    onError: (err: Error) => {
      setStatus(err.message || 'Failed to teach Kassandra.')
    },
  })

  const saveSelectedGap = () => {
    if (!selectedGap || !selectedKey) return
    const answer = (answers[selectedKey] || '').trim()
    if (answer.length < 4) {
      setStatus('Write a short answer for this question first.')
      return
    }
    teachMutation.mutate({
      text: answer,
      gap_memory_id: selectedGap.memory_id,
      question: selectedGap.question,
      extra: (extras[selectedKey] || '').trim() || null,
      mode: 'gap',
    })
  }

  const saveFreeform = () => {
    const text = freeform.trim()
    if (text.length < 8) {
      setStatus('Add a bit more detail in the extra context field.')
      return
    }
    teachMutation.mutate({
      text,
      mode: 'extra',
    })
  }

  return (
    <div className="min-w-0 overflow-x-hidden p-4 sm:p-6 lg:p-8">
      <PageHeader
        title="Teach Kassandra"
        description="Answer each knowledge gap, or add extra institutional context — Sibyl preserves it."
      />

      {!activeProject ? (
        <Card className="p-5">
          <p className="text-sm text-[var(--color-text-muted)]">
            Connect and activate a project first, then Kassandra can bootstrap from the repo and
            interview you only on what remains unknown.
          </p>
          <Link to="/dashboard/projects" className="mt-4 inline-block">
            <Button>Go to Projects</Button>
          </Link>
        </Card>
      ) : (
        <div className="space-y-8">
          <div className="flex flex-wrap items-center gap-2 text-sm text-[var(--color-text-muted)]">
            <span>Active project</span>
            <Badge variant="cyan">{activeProject.repo_full_name}</Badge>
            <Button
              size="sm"
              variant="outline"
              loading={understandingQuery.isFetching}
              loadingText="Refreshing…"
              onClick={() => void understandingQuery.refetch()}
            >
              Refresh understanding
            </Button>
          </div>

          {understandingQuery.isLoading ? (
            <LoadingState message="Loading Sibyl project understanding…" />
          ) : understandingQuery.data ? (
            <UnderstandingSummary data={understandingQuery.data} />
          ) : (
            <Card className="p-5 text-sm text-[var(--color-text-muted)]">
              No bootstrap summary yet. Run Analyze on the project to reconstruct from the repository
              first.
            </Card>
          )}

          <Card className="p-5 sm:p-6">
            <h2 className="text-lg font-semibold">Answer knowledge gaps</h2>
            <p className="mt-2 text-sm text-[var(--color-text-muted)]">
              Select a question, answer it, optionally add extra notes for that answer, then save.
              Answered gaps are removed from this list and stored in Sibyl as confirmed.
            </p>

            {gaps.length === 0 ? (
              <p className="mt-4 text-sm text-[var(--color-text-muted)]">
                No open knowledge gaps. You can still add extra context below.
              </p>
            ) : (
              <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,14rem)_1fr]">
                <div className="space-y-2">
                  {gaps.map((gap, index) => {
                    const key = gapKey(gap, index)
                    const active = key === selectedKey
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setSelectedKey(key)}
                        className={`w-full rounded-md border px-3 py-2.5 text-left text-sm transition-colors ${
                          active
                            ? 'border-[var(--color-cyan)]/50 bg-[var(--color-cyan)]/10 text-[var(--color-text)]'
                            : 'border-[var(--color-border-subtle)] text-[var(--color-text-muted)] hover:border-[var(--color-border)]'
                        }`}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={gap.priority === 'high' ? 'warning' : 'default'}>
                            {gap.priority || 'medium'}
                          </Badge>
                          <span className="text-xs text-[var(--color-text-dim)]">
                            {index + 1}/{gaps.length}
                          </span>
                        </div>
                        <p className="mt-1.5 line-clamp-3 leading-snug">{gap.question}</p>
                      </button>
                    )
                  })}
                </div>

                <div className="min-w-0">
                  {selectedGap && selectedKey ? (
                    <div className="space-y-4">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
                          Selected question
                        </p>
                        <p className="mt-1 text-base font-medium">{selectedGap.question}</p>
                        {selectedGap.reason && (
                          <p className="mt-2 text-sm text-[var(--color-text-muted)]">
                            {selectedGap.reason}
                          </p>
                        )}
                      </div>

                      <div>
                        <label
                          htmlFor="gap-answer"
                          className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-dim)]"
                        >
                          Your answer
                        </label>
                        <textarea
                          id="gap-answer"
                          value={answers[selectedKey] || ''}
                          onChange={(e) =>
                            setAnswers((prev) => ({ ...prev, [selectedKey]: e.target.value }))
                          }
                          rows={5}
                          placeholder="Explain the WHY in your own words…"
                          className={`mt-2 w-full resize-y ${glassFieldClass} ${glassFieldDefaultClass}`}
                        />
                      </div>

                      <div>
                        <label
                          htmlFor="gap-extra"
                          className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-dim)]"
                        >
                          Extra for this answer (optional)
                        </label>
                        <textarea
                          id="gap-extra"
                          value={extras[selectedKey] || ''}
                          onChange={(e) =>
                            setExtras((prev) => ({ ...prev, [selectedKey]: e.target.value }))
                          }
                          rows={3}
                          placeholder="Dates, people, incidents, alternatives considered…"
                          className={`mt-2 w-full resize-y ${glassFieldClass} ${glassFieldDefaultClass}`}
                        />
                      </div>

                      <Button
                        loading={teachMutation.isPending}
                        loadingText="Saving to Sibyl…"
                        disabled={(answers[selectedKey] || '').trim().length < 4}
                        onClick={saveSelectedGap}
                      >
                        Save this answer
                      </Button>
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--color-text-muted)]">
                      Select a question on the left to answer it.
                    </p>
                  )}
                </div>
              </div>
            )}
          </Card>

          <Card className="p-5 sm:p-6">
            <h2 className="text-lg font-semibold">Extra institutional context</h2>
            <p className="mt-2 text-sm text-[var(--color-text-muted)]">
              Not tied to a gap question — anything else Kassandra should remember (decisions,
              incidents, constraints, team conventions).
            </p>
            <textarea
              value={freeform}
              onChange={(e) => setFreeform(e.target.value)}
              rows={5}
              placeholder="Example: We originally used MongoDB but migrated to PostgreSQL because…"
              className={`mt-4 w-full resize-y ${glassFieldClass} ${glassFieldDefaultClass}`}
            />
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                loading={teachMutation.isPending}
                loadingText="Saving to Sibyl…"
                disabled={freeform.trim().length < 8}
                onClick={saveFreeform}
              >
                Save extra context
              </Button>
            </div>
          </Card>

          {status && (
            <p className="text-sm text-[var(--color-text-muted)]">{status}</p>
          )}
        </div>
      )}
    </div>
  )
}

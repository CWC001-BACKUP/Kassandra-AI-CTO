import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { LoadingState } from '../../components/ui/LoadingState'
import { PageHeader } from '../../components/ui/PageHeader'
import { glassFieldClass, glassFieldDefaultClass } from '../../components/ui/surfaceStyles'
import { projectsApi } from '../../services/api'
import type { MemoryCard, ProjectUnderstanding } from '../../types'

type TabId = 'review' | 'questions' | 'browse' | 'add'

function ConfidenceBadge({ value }: { value?: string | null }) {
  const v = (value || '').toLowerCase()
  if (v === 'confirmed' || v === 'high') return <Badge variant="success">confirmed</Badge>
  if (v === 'inferred' || v === 'medium') return <Badge variant="warning">inferred</Badge>
  if (v === 'observed') return <Badge variant="cyan">from repo</Badge>
  return <Badge>{value || 'unknown'}</Badge>
}

function StatChip({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface)]/40 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
        {label}
      </p>
      <p className="mt-0.5 font-display text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function MemoryBody({ item, expanded }: { item: MemoryCard; expanded?: boolean }) {
  const text =
    [item.content, item.decision, item.reason, item.outcome].filter(Boolean).join('\n\n') ||
    item.title ||
    ''
  return (
    <div
      className={`mt-2 text-sm text-[var(--color-text-muted)] ${
        expanded ? 'max-h-48 overflow-y-auto whitespace-pre-wrap pr-1' : 'line-clamp-3'
      }`}
    >
      {text}
    </div>
  )
}

function FactReviewCard({
  item,
  busy,
  onConfirm,
  onReject,
  onCorrect,
}: {
  item: MemoryCard
  busy?: boolean
  onConfirm: () => void
  onReject: (note: string) => void
  onCorrect: (note: string) => void
}) {
  const [mode, setMode] = useState<'idle' | 'reject' | 'correct'>('idle')
  const [note, setNote] = useState('')
  const verified = (item.tags || []).includes('human_verified')
  const rejected = item.status === 'rejected' || (item.tags || []).includes('human_rejected')

  return (
    <div className="rounded-lg border border-[var(--color-border-subtle)] p-4 transition-colors hover:border-[var(--color-border)]">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium leading-snug">{item.title || 'Untitled fact'}</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            <ConfidenceBadge value={item.confidence} />
            {item.type && <Badge>{item.type.replace(/_/g, ' ')}</Badge>}
            {verified && <Badge variant="success">you verified</Badge>}
            {rejected && <Badge variant="warning">marked false</Badge>}
          </div>
        </div>
      </div>
      <MemoryBody item={item} expanded />
      {(item.affected_components?.length || 0) > 0 && (
        <p className="mt-2 text-[11px] text-[var(--color-text-dim)]">
          Affects: {item.affected_components!.join(', ')}
        </p>
      )}

      {!rejected && (
        <div className="mt-3 flex flex-wrap gap-2">
          {mode === 'idle' ? (
            <>
              <Button size="sm" disabled={busy || verified} onClick={onConfirm}>
                {verified ? 'Verified' : 'True'}
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => setMode('reject')}>
                False
              </Button>
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => setMode('correct')}>
                Correct…
              </Button>
            </>
          ) : (
            <div className="w-full space-y-2">
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                placeholder={
                  mode === 'reject'
                    ? 'Optional: why is this wrong?'
                    : 'What should Kassandra remember instead?'
                }
                className={`w-full resize-y ${glassFieldClass} ${glassFieldDefaultClass}`}
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  loading={busy}
                  disabled={mode === 'correct' && note.trim().length < 4}
                  onClick={() => {
                    if (mode === 'reject') onReject(note.trim())
                    else onCorrect(note.trim())
                    setMode('idle')
                    setNote('')
                  }}
                >
                  {mode === 'reject' ? 'Mark false' : 'Save correction'}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setMode('idle')
                    setNote('')
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ScrollSection({
  title,
  empty,
  items,
  children,
}: {
  title: string
  empty: string
  items: MemoryCard[]
  children?: (item: MemoryCard, index: number) => ReactNode
}) {
  return (
    <Card className="flex min-h-0 flex-col p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="text-xs tabular-nums text-[var(--color-text-dim)]">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">{empty}</p>
      ) : (
        <div className="mt-3 max-h-72 space-y-3 overflow-y-auto pr-1 sm:max-h-80">
          {items.map((item, index) =>
            children ? (
              <div key={item.memory_id || `${item.title}-${index}`}>{children(item, index)}</div>
            ) : (
              <div
                key={item.memory_id || `${item.title}-${index}`}
                className="rounded-md border border-[var(--color-border-subtle)] p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <p className="min-w-0 flex-1 text-sm font-medium">{item.title}</p>
                  <ConfidenceBadge value={item.confidence} />
                </div>
                <MemoryBody item={item} expanded />
              </div>
            ),
          )}
        </div>
      )}
    </Card>
  )
}

type GapItem = ProjectUnderstanding['knowledge_gaps'][number]

export function TeachPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<TabId>('review')
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [extras, setExtras] = useState<Record<string, string>>({})
  const [freeform, setFreeform] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [reviewBusyId, setReviewBusyId] = useState<string | null>(null)
  const [pendingPreview, setPendingPreview] = useState<{
    pending_id?: string
    candidates: Array<{
      index?: number
      title?: string | null
      decision?: string | null
      reason?: string | null
      content?: string | null
      type?: string | null
    }>
    mode: 'gap' | 'extra'
    question?: string | null
  } | null>(null)
  const [selectedCandidateIdx, setSelectedCandidateIdx] = useState<Set<number>>(new Set())

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

  const data = understandingQuery.data
  const gaps = data?.knowledge_gaps ?? []
  const reviewable = data?.reviewable_facts ?? []

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

  useEffect(() => {
    if (!data) return
    if ((data.counts.knowledge_gaps ?? 0) > 0 && tab === 'review' && reviewable.length === 0) {
      // keep review tab; user can switch
    }
  }, [data, tab, reviewable.length])

  const selectedGap = useMemo(() => {
    if (!selectedKey) return null
    return gaps.find((g, i) => gapKey(g, i) === selectedKey) ?? null
  }, [gaps, selectedKey])

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['project-understanding'] })
    void queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
  }

  const reviewMutation = useMutation({
    mutationFn: (payload: {
      memoryId: string
      action: 'confirm' | 'reject' | 'correct'
      note?: string
    }) => projectsApi.reviewMemory(activeProject!.id, payload.memoryId, payload.action, payload.note),
    onMutate: (vars) => setReviewBusyId(vars.memoryId),
    onSettled: () => setReviewBusyId(null),
    onSuccess: (result) => {
      invalidate()
      if (result.action === 'confirm') setStatus('Marked true and confirmed in Sibyl.')
      else if (result.action === 'reject') setStatus('Marked false in Sibyl.')
      else setStatus('Correction saved to Sibyl.')
    },
    onError: (err: Error) => setStatus(err.message || 'Review failed.'),
  })

  const teachMutation = useMutation({
      mutationFn: (payload: {
      text: string
      gap_memory_id?: string | null
      question?: string | null
      extra?: string | null
      mode: 'gap' | 'extra'
      confirm?: boolean | null
      pending_id?: string | null
      selected_indices?: number[] | null
    }) =>
      projectsApi.teach(activeProject!.id, payload.text, {
        gap_memory_id: payload.gap_memory_id,
        question: payload.question,
        extra: payload.extra,
        confirm: payload.confirm,
        pending_id: payload.pending_id,
        selected_indices: payload.selected_indices,
      }),
    onSuccess: (result, variables) => {
      invalidate()
      if (result.awaiting_confirmation && result.pending) {
        const candidates = result.pending.candidates ?? []
        setPendingPreview({
          pending_id: result.pending.pending_id,
          candidates,
          mode: variables.mode,
          question: variables.question,
        })
        setSelectedCandidateIdx(new Set(candidates.map((_, i) => i)))
        setStatus(
          result.reply ||
            `Review ${candidates.length} candidate memories — keep the ones you want, then confirm.`,
        )
        return
      }
      if (result.stored || result.gap_resolved || result.verified) {
        setStatus(result.reply || 'Saved to Sibyl.')
        setPendingPreview(null)
        setSelectedCandidateIdx(new Set())
        if (variables.mode === 'gap' && selectedKey) {
          setAnswers((prev) => {
            const next = { ...prev }
            delete next[selectedKey]
            return next
          })
          setExtras((prev) => {
            const next = { ...prev }
            delete next[selectedKey]
            return next
          })
        } else {
          setFreeform('')
        }
      } else {
        setStatus(result.reason || result.reply || 'Nothing stored.')
        if (variables.confirm === false) setPendingPreview(null)
      }
    },
    onError: (err: Error) => setStatus(err.message || 'Failed to teach Kassandra.'),
  })

  const tabs: Array<{ id: TabId; label: string; count?: number }> = [
    { id: 'review', label: 'Review facts', count: reviewable.length },
    { id: 'questions', label: 'Questions', count: gaps.length },
    { id: 'browse', label: 'Browse all' },
    { id: 'add', label: 'Add context' },
  ]

  return (
    <div className="min-w-0 overflow-x-hidden p-4 sm:p-6 lg:p-8">
      <PageHeader
        title="Teach Kassandra"
        description="Verify what the repo suggested, answer open questions, add missing WHY — Sibyl keeps it."
      />

      {!activeProject ? (
        <Card className="p-5">
          <p className="text-sm text-[var(--color-text-muted)]">
            Connect and activate a project first.
          </p>
          <Link to="/dashboard/projects" className="mt-4 inline-block">
            <Button>Go to Projects</Button>
          </Link>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2 text-sm text-[var(--color-text-muted)]">
              <span>Active</span>
              <Badge variant="cyan">{activeProject.repo_full_name}</Badge>
            </div>
            <Button
              size="sm"
              variant="outline"
              loading={understandingQuery.isFetching}
              loadingText="Refreshing…"
              onClick={() => void understandingQuery.refetch()}
            >
              Refresh
            </Button>
          </div>

          {understandingQuery.isLoading ? (
            <LoadingState message="Loading project understanding…" />
          ) : data ? (
            <>
              <Card className="p-4 sm:p-5">
                <p className="text-sm text-[var(--color-text-muted)]">{data.headline}</p>
                <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <StatChip label="From repo" value={data.counts.observed ?? 0} />
                  <StatChip label="Inferred" value={data.counts.inferred ?? 0} />
                  <StatChip label="Confirmed" value={data.counts.confirmed ?? 0} />
                  <StatChip label="Questions" value={data.counts.knowledge_gaps ?? 0} />
                </div>
              </Card>

              <div className="flex gap-1 overflow-x-auto border-b border-[var(--color-border-subtle)] pb-px">
                {tabs.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTab(t.id)}
                    className={`shrink-0 rounded-t-md px-3 py-2 text-sm font-medium transition-colors ${
                      tab === t.id
                        ? 'border border-b-transparent border-[var(--color-border-subtle)] bg-[var(--color-bg)] text-[var(--color-cyan)]'
                        : 'text-[var(--color-text-dim)] hover:text-[var(--color-text)]'
                    }`}
                  >
                    {t.label}
                    {typeof t.count === 'number' && t.count > 0 && (
                      <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--color-warning)]/15 px-1 text-[10px] text-[var(--color-warning)]">
                        {t.count}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {tab === 'review' && (
                <div className="space-y-3">
                  <p className="text-sm text-[var(--color-text-muted)]">
                    Optional: mark each fact True, False, or Correct. Skip anything you do not care
                    about.
                  </p>
                  {reviewable.length === 0 ? (
                    <Card className="p-5 text-sm text-[var(--color-text-muted)]">
                      No facts waiting for review. Analyze a project or open Questions.
                    </Card>
                  ) : (
                    <div className="max-h-[min(36rem,70dvh)] space-y-3 overflow-y-auto pr-1">
                      {reviewable.map((item) => (
                        <FactReviewCard
                          key={item.memory_id || item.title}
                          item={item}
                          busy={reviewBusyId === item.memory_id}
                          onConfirm={() =>
                            item.memory_id &&
                            reviewMutation.mutate({ memoryId: item.memory_id, action: 'confirm' })
                          }
                          onReject={(note) =>
                            item.memory_id &&
                            reviewMutation.mutate({
                              memoryId: item.memory_id,
                              action: 'reject',
                              note,
                            })
                          }
                          onCorrect={(note) =>
                            item.memory_id &&
                            reviewMutation.mutate({
                              memoryId: item.memory_id,
                              action: 'correct',
                              note,
                            })
                          }
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}

              {tab === 'questions' && (
                <Card className="p-4 sm:p-5">
                  {gaps.length === 0 ? (
                    <p className="text-sm text-[var(--color-text-muted)]">
                      No open questions. Add extra context anytime.
                    </p>
                  ) : (
                    <div className="grid gap-4 lg:grid-cols-[minmax(0,15rem)_1fr]">
                      <div className="max-h-80 space-y-2 overflow-y-auto pr-1 lg:max-h-[28rem]">
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
                                  ? 'border-[var(--color-cyan)]/50 bg-[var(--color-cyan)]/10'
                                  : 'border-[var(--color-border-subtle)] hover:border-[var(--color-border)]'
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                <Badge variant={gap.priority === 'high' ? 'warning' : 'default'}>
                                  {gap.priority || 'medium'}
                                </Badge>
                                <span className="text-[10px] text-[var(--color-text-dim)]">
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
                              <p className="text-base font-medium">{selectedGap.question}</p>
                              {selectedGap.reason && (
                                <p className="mt-2 max-h-24 overflow-y-auto text-sm text-[var(--color-text-muted)]">
                                  {selectedGap.reason}
                                </p>
                              )}
                            </div>
                            <textarea
                              value={answers[selectedKey] || ''}
                              onChange={(e) =>
                                setAnswers((prev) => ({ ...prev, [selectedKey]: e.target.value }))
                              }
                              rows={4}
                              placeholder="Your answer…"
                              className={`w-full resize-y ${glassFieldClass} ${glassFieldDefaultClass}`}
                            />
                            <textarea
                              value={extras[selectedKey] || ''}
                              onChange={(e) =>
                                setExtras((prev) => ({ ...prev, [selectedKey]: e.target.value }))
                              }
                              rows={2}
                              placeholder="Optional notes (dates, people, incidents…)"
                              className={`w-full resize-y ${glassFieldClass} ${glassFieldDefaultClass}`}
                            />
                            <Button
                              loading={teachMutation.isPending && !pendingPreview}
                              loadingText="Extracting…"
                              disabled={(answers[selectedKey] || '').trim().length < 4}
                              onClick={() =>
                                teachMutation.mutate({
                                  text: (answers[selectedKey] || '').trim(),
                                  gap_memory_id: selectedGap.memory_id,
                                  question: selectedGap.question,
                                  extra: (extras[selectedKey] || '').trim() || null,
                                  mode: 'gap',
                                })
                              }
                            >
                              Extract & review
                            </Button>
                          </div>
                        ) : (
                          <p className="text-sm text-[var(--color-text-muted)]">
                            Select a question.
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {tab === 'browse' && (
                <div className="grid gap-4 lg:grid-cols-2">
                  <ScrollSection
                    title="Architecture"
                    empty="No architecture observations yet."
                    items={data.architecture}
                  />
                  <ScrollSection
                    title="History & evolution"
                    empty="No historical signals yet."
                    items={data.historical_evolution}
                  />
                  <ScrollSection
                    title="Problems & incidents"
                    empty="No incidents or conflicts recorded."
                    items={data.problems ?? []}
                  />
                  <ScrollSection
                    title="Inferred (optional)"
                    empty="No inferences yet."
                    items={data.inferred ?? []}
                  />
                  <div className="lg:col-span-2">
                    <ScrollSection
                      title="Already confirmed by you"
                      empty="Nothing human-confirmed yet."
                      items={data.confirmed ?? []}
                    />
                  </div>
                </div>
              )}

              {tab === 'add' && (
                <Card className="p-4 sm:p-5">
                  <h2 className="text-base font-semibold">Extra institutional context</h2>
                  <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                    Decisions, incidents, constraints, conventions — anything the repo cannot say.
                  </p>
                  <textarea
                    value={freeform}
                    onChange={(e) => setFreeform(e.target.value)}
                    rows={5}
                    placeholder="We migrated from X to Y because…"
                    className={`mt-4 w-full resize-y ${glassFieldClass} ${glassFieldDefaultClass}`}
                  />
                  <Button
                    className="mt-4"
                    variant="outline"
                    loading={teachMutation.isPending && !pendingPreview}
                    loadingText="Extracting…"
                    disabled={freeform.trim().length < 8}
                    onClick={() =>
                      teachMutation.mutate({ text: freeform.trim(), mode: 'extra' })
                    }
                  >
                    Extract & review
                  </Button>
                </Card>
              )}
            </>
          ) : (
            <Card className="p-5 text-sm text-[var(--color-text-muted)]">
              No understanding yet. Run Analyze on the project first.
            </Card>
          )}

          {pendingPreview && (
            <Card className="border-[var(--color-cyan)]/30 p-4 sm:p-5">
              <h2 className="text-base font-semibold">Confirm before saving</h2>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                Toggle each candidate on or off. Only selected ones are saved to Sibyl; the rest are
                discarded.
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <button
                  type="button"
                  className="text-[var(--color-cyan)] hover:underline"
                  onClick={() =>
                    setSelectedCandidateIdx(
                      new Set(pendingPreview.candidates.map((_, i) => i)),
                    )
                  }
                >
                  Select all
                </button>
                <span className="text-[var(--color-text-dim)]">·</span>
                <button
                  type="button"
                  className="text-[var(--color-cyan)] hover:underline"
                  onClick={() => setSelectedCandidateIdx(new Set())}
                >
                  Select none
                </button>
                <span className="text-[var(--color-text-dim)]">
                  · {selectedCandidateIdx.size} of {pendingPreview.candidates.length} selected
                </span>
              </div>
              <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
                {pendingPreview.candidates.map((c, i) => {
                  const checked = selectedCandidateIdx.has(i)
                  const body = [c.decision, c.reason, c.content].filter(Boolean).join('\n\n')
                  return (
                    <label
                      key={`${c.title}-${i}`}
                      className={`flex cursor-pointer gap-3 rounded-md border p-3 text-sm transition-colors ${
                        checked
                          ? 'border-[var(--color-cyan)]/40 bg-[var(--color-cyan)]/5'
                          : 'border-[var(--color-border-subtle)] opacity-70'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          setSelectedCandidateIdx((prev) => {
                            const next = new Set(prev)
                            if (next.has(i)) next.delete(i)
                            else next.add(i)
                            return next
                          })
                        }}
                        className="mt-1 accent-[var(--color-cyan)]"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
                            #{i + 1}
                          </span>
                          {c.type && <Badge>{String(c.type).replace(/_/g, ' ')}</Badge>}
                          <Badge variant={checked ? 'success' : 'default'}>
                            {checked ? 'keep' : 'discard'}
                          </Badge>
                        </div>
                        <p className="mt-1 font-medium">
                          {c.decision || c.title || `Memory ${i + 1}`}
                        </p>
                        {body && body !== (c.decision || c.title) && (
                          <p className="mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap text-[var(--color-text-muted)]">
                            {body}
                          </p>
                        )}
                      </div>
                    </label>
                  )
                })}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  loading={teachMutation.isPending}
                  loadingText="Saving…"
                  disabled={selectedCandidateIdx.size === 0}
                  onClick={() =>
                    teachMutation.mutate({
                      text: '',
                      mode: pendingPreview.mode,
                      confirm: true,
                      pending_id: pendingPreview.pending_id,
                      question: pendingPreview.question,
                      selected_indices: Array.from(selectedCandidateIdx).sort((a, b) => a - b),
                    })
                  }
                >
                  Save selected ({selectedCandidateIdx.size})
                </Button>
                <Button
                  variant="outline"
                  disabled={teachMutation.isPending}
                  onClick={() => {
                    setSelectedCandidateIdx(
                      new Set(pendingPreview.candidates.map((_, i) => i)),
                    )
                    teachMutation.mutate({
                      text: '',
                      mode: pendingPreview.mode,
                      confirm: true,
                      pending_id: pendingPreview.pending_id,
                      question: pendingPreview.question,
                      selected_indices: pendingPreview.candidates.map((_, i) => i),
                    })
                  }}
                >
                  Save all
                </Button>
                <Button
                  variant="ghost"
                  disabled={teachMutation.isPending}
                  onClick={() =>
                    teachMutation.mutate({
                      text: '',
                      mode: pendingPreview.mode,
                      confirm: false,
                      pending_id: pendingPreview.pending_id,
                    })
                  }
                >
                  Discard all
                </Button>
              </div>
            </Card>
          )}

          {status && (
            <p className="whitespace-pre-wrap text-sm text-[var(--color-text-muted)]">{status}</p>
          )}
        </div>
      )}
    </div>
  )
}

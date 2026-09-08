import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { EvidenceList } from '../../components/chat/EvidenceList'
import { Button } from '../../components/ui/Button'
import { buttonClasses } from '../../components/ui/buttonStyles'
import { glassFieldClass, glassFieldDefaultClass } from '../../components/ui/surfaceStyles'
import { ChatTypingIndicator } from '../../components/ui/ChatTypingIndicator'
import { LoadingState } from '../../components/ui/LoadingState'
import { chatApi, dashboardApi, projectsApi } from '../../services/api'
import { ApiError } from '../../services/api'
import type { ChatMessage } from '../../types'

const SIBYL_STORAGE_KEY = 'kassandra-sibyl-enabled'

function readSibylPreference(): boolean {
  try {
    const stored = localStorage.getItem(SIBYL_STORAGE_KEY)
    if (stored === 'false') return false
    if (stored === 'true') return true
  } catch {
    /* ignore */
  }
  return true
}

const suggestions = [
  'What is the tech stack?',
  'How does authentication work?',
  'What changed recently?',
]

const compareSuggestions = [
  'Compare both repos — tech stack and activity',
  'Give me a unified report across my repositories',
  'Which repo has more recent commits?',
]

function formatSessionDate(iso: string) {
  const date = new Date(iso)
  const now = new Date()
  const sameDay =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear()
  if (sameDay) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

export function ChatPage() {
  const queryClient = useQueryClient()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sibylEnabled, setSibylEnabled] = useState(readSibylPreference)
  const [sessionsOpen, setSessionsOpen] = useState(false)
  const [compareMode, setCompareMode] = useState(false)
  const [compareProjectIds, setCompareProjectIds] = useState<string[]>([])
  const [bootstrapBlocked, setBootstrapBlocked] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const bootstrapStartedRef = useRef(false)
  const sessionIdRef = useRef<string | null>(null)
  sessionIdRef.current = sessionId

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
  })

  const statsQuery = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: dashboardApi.stats,
  })
  const gapCount = statsQuery.data?.knowledge_gap_count ?? 0

  const projects = projectsQuery.data ?? []
  const selectedProject =
    projects.find((p) => p.id === selectedProjectId) ??
    projects.find((p) => p.is_active) ??
    projects[0] ??
    null

  useEffect(() => {
    if (selectedProjectId || projects.length === 0) return
    const defaultProject = projects.find((p) => p.is_active) ?? projects[0]
    setSelectedProjectId(defaultProject.id)
  }, [projects, selectedProjectId])

  const projectNameById = (projectId: string | null | undefined) =>
    projects.find((p) => p.id === projectId)?.repo_full_name

  const sessionsQuery = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: chatApi.listSessions,
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status === 401) && failureCount < 2,
  })

  const loadSessionMutation = useMutation({
    mutationFn: (id: string) => chatApi.getSession(id),
    onMutate: () => {
      setMessages([])
    },
    onSuccess: (detail) => {
      setSessionId(detail.id)
      setMessages(detail.messages)
      if (detail.project_id) {
        setSelectedProjectId(detail.project_id)
      }
    },
    onError: () => {
      if (!sessionIdRef.current) {
        bootstrapStartedRef.current = false
      }
    },
  })

  const { mutate: loadSession } = loadSessionMutation

  const createSessionMutation = useMutation({
    mutationFn: (projectId?: string | null) =>
      chatApi.createSession(projectId ?? selectedProjectId ?? null),
    onSuccess: (detail) => {
      setSessionId(detail.id)
      setMessages(detail.messages)
      if (detail.project_id) {
        setSelectedProjectId(detail.project_id)
      }
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    },
    onError: (error: Error) => {
      if (!sessionIdRef.current) {
        bootstrapStartedRef.current = false
      }
      if (error instanceof ApiError && error.status === 401) {
        setBootstrapBlocked(true)
      }
    },
  })

  const chatMutation = useMutation({
    mutationFn: (message: string) =>
      chatApi.send({
        message,
        project_id: selectedProjectId,
        project_ids:
          compareMode && compareProjectIds.length >= 2 ? compareProjectIds : undefined,
        session_id: sessionId,
        sibyl_enabled: sibylEnabled,
      }),
    onSuccess: (response) => {
      if (response.session_id && response.session_id !== sessionId) {
        setSessionId(response.session_id)
      }
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: response.reply,
          evidence: response.evidence,
          created_at: new Date().toISOString(),
        },
      ])
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    },
    onError: (error: Error) => {
      const detail = error instanceof ApiError ? error.detail : error.message
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `Sorry, something went wrong: ${detail ?? 'unknown error'}`,
          created_at: new Date().toISOString(),
        },
      ])
    },
  })

  const { mutate: createSession } = createSessionMutation

  useEffect(() => {
    if (bootstrapBlocked || sessionId) return
    if (sessionsQuery.isLoading || sessionsQuery.isError) return
    if (createSessionMutation.isPending || loadSessionMutation.isPending) return
    if (bootstrapStartedRef.current) return
    if (!sessionsQuery.isFetched) return
    if (projectsQuery.isLoading) return
    // Wait until default repo selection runs when the user has projects.
    if (projects.length > 0 && !selectedProjectId) return

    const sessions = sessionsQuery.data ?? []
    const projectId = selectedProjectId

    if (projectId) {
      const match = sessions.find((s) => s.project_id === projectId)
      bootstrapStartedRef.current = true
      if (match) {
        loadSession(match.id)
      } else {
        createSession(projectId)
      }
      return
    }

    if (sessions.length > 0) {
      bootstrapStartedRef.current = true
      loadSession(sessions[0].id)
      return
    }

    bootstrapStartedRef.current = true
    createSession(null)
  }, [
    bootstrapBlocked,
    sessionId,
    sessionsQuery.isLoading,
    sessionsQuery.isError,
    sessionsQuery.isFetched,
    sessionsQuery.data,
    createSessionMutation.isPending,
    loadSessionMutation.isPending,
    projectsQuery.isLoading,
    projects.length,
    selectedProjectId,
    loadSession,
    createSession,
  ])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, chatMutation.isPending])

  const deleteSessionMutation = useMutation({
    mutationFn: (id: string) => chatApi.deleteSession(id),
    onSuccess: (_data, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      if (sessionId === deletedId) {
        setSessionId(null)
        setMessages([])
        const remaining = (sessionsQuery.data ?? []).filter((s) => s.id !== deletedId)
        if (remaining.length > 0) {
          setSessionId(remaining[0].id)
          loadSession(remaining[0].id)
        } else {
          createSessionMutation.mutate(selectedProjectId)
        }
      }
    },
  })

  const handleSend = () => {
    const text = input.trim()
    if (!text || chatMutation.isPending || !sessionId) return

    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        role: 'user',
        content: text,
        created_at: new Date().toISOString(),
      },
    ])
    setInput('')
    chatMutation.mutate(text)
  }

  const handleNewChat = () => {
    createSessionMutation.mutate(selectedProjectId)
  }

  const handleRepoChange = (projectId: string) => {
    if (!projectId || projectId === selectedProjectId) return
    setSelectedProjectId(projectId)
    createSessionMutation.mutate(projectId)
  }

  const toggleCompareMode = () => {
    setCompareMode((prev) => {
      const next = !prev
      if (next && selectedProjectId) {
        setCompareProjectIds([selectedProjectId])
      } else {
        setCompareProjectIds([])
      }
      return next
    })
  }

  const toggleCompareProject = (projectId: string) => {
    setCompareProjectIds((prev) => {
      if (prev.includes(projectId)) {
        return prev.filter((id) => id !== projectId)
      }
      return [...prev, projectId]
    })
    if (!selectedProjectId) {
      setSelectedProjectId(projectId)
    }
  }

  const activeSuggestions =
    compareMode && compareProjectIds.length >= 2 ? compareSuggestions : suggestions

  const toggleSibyl = () => {
    setSibylEnabled((prev) => {
      const next = !prev
      try {
        localStorage.setItem(SIBYL_STORAGE_KEY, String(next))
      } catch {
        /* ignore */
      }
      return next
    })
  }

  const handleSelectSession = (id: string) => {
    if (id !== sessionId && !loadSessionMutation.isPending) {
      setSessionId(id)
      loadSession(id)
    }
    setSessionsOpen(false)
  }

  const isBootstrapping =
    sessionsQuery.isLoading ||
    (!sessionId &&
      (createSessionMutation.isPending ||
        loadSessionMutation.isPending ||
        (sessionsQuery.data?.length ?? 0) === 0))

  const isSwitchingSession =
    loadSessionMutation.isPending || createSessionMutation.isPending

  const chatLoadingMessage = createSessionMutation.isPending
    ? 'Creating chat…'
    : 'Loading chat…'

  return (
    <div className="flex min-h-[calc(100dvh-4.5rem)] flex-col lg:min-h-screen lg:h-screen">
      {sessionsOpen && (
        <button
          type="button"
          aria-label="Close chat list"
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-[2px] lg:hidden"
          onClick={() => setSessionsOpen(false)}
        />
      )}

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <aside
        className={`glass-sidebar fixed left-0 top-0 z-40 flex w-[min(100%,18rem)] shrink-0 flex-col transition-transform duration-200 bottom-[calc(4.5rem+env(safe-area-inset-bottom,0px))] lg:static lg:z-auto lg:h-auto lg:w-64 lg:translate-x-0 lg:bottom-auto ${
          sessionsOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="border-b border-[var(--color-border-subtle)] p-4">
          <Button
            className="w-full"
            onClick={handleNewChat}
            loading={createSessionMutation.isPending}
            loadingText="Creating…"
          >
            New chat
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {sessionsQuery.isLoading ? (
            <p className="px-2 py-3 text-xs text-[var(--color-text-dim)]">Loading chats…</p>
          ) : (sessionsQuery.data ?? []).length === 0 ? (
            <p className="px-2 py-3 text-xs text-[var(--color-text-dim)]">No chats yet</p>
          ) : (
            <ul className="space-y-1">
              {(sessionsQuery.data ?? []).map((session) => (
                <li key={session.id}>
                  <button
                    type="button"
                    onClick={() => handleSelectSession(session.id)}
                    disabled={loadSessionMutation.isPending}
                    className={`btn-glass btn-glass-session group disabled:opacity-60 ${
                      session.id === sessionId ? 'btn-glass-session-active' : ''
                    } ${loadSessionMutation.isPending && loadSessionMutation.variables === session.id ? 'opacity-80' : ''}`}
                  >
                    <span className="line-clamp-2 text-sm">{session.title}</span>
                    {projectNameById(session.project_id) && (
                      <span className="truncate text-[10px] text-[var(--color-cyan)]/80">
                        {projectNameById(session.project_id)}
                      </span>
                    )}
                    <span className="shrink-0 text-[10px] opacity-60">
                      {formatSessionDate(session.updated_at)}
                    </span>
                  </button>
                  {session.id === sessionId && (
                    <button
                      type="button"
                      onClick={() => deleteSessionMutation.mutate(session.id)}
                      className={`${buttonClasses('link', 'sm')} ml-3 text-[10px] text-[var(--color-text-dim)] hover:text-red-400`}
                    >
                      Delete chat
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-[var(--color-border-subtle)] px-3 py-2 sm:px-4">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="shrink-0 px-2 lg:hidden"
              onClick={() => setSessionsOpen(true)}
              aria-label="Open chat list"
            >
              Chats
            </Button>

            {projects.length === 0 ? (
              <p className="min-w-0 flex-1 truncate text-sm text-[var(--color-text-dim)]">
                No projects —{' '}
                <Link to="/dashboard/projects" className="text-[var(--color-cyan)] hover:underline">
                  add a repo
                </Link>
              </p>
            ) : compareMode ? (
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="shrink-0 text-sm text-[var(--color-text-muted)]">Compare</span>
                  {compareProjectIds.length >= 2 && (
                    <span className="text-xs text-[var(--color-cyan)]">
                      {compareProjectIds.length} selected
                    </span>
                  )}
                </div>
                <div className="mt-1.5 max-h-28 space-y-0.5 overflow-y-auto rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg)]/40 px-2 py-1.5">
                  {projects.map((project) => {
                    const checked = compareProjectIds.includes(project.id)
                    return (
                      <label
                        key={project.id}
                        className="flex cursor-pointer items-center gap-2 py-0.5 text-xs sm:text-sm"
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleCompareProject(project.id)}
                          className="accent-[var(--color-cyan)]"
                        />
                        <span className="min-w-0 truncate">{project.repo_full_name}</span>
                      </label>
                    )
                  })}
                </div>
              </div>
            ) : (
              <select
                value={selectedProjectId ?? selectedProject?.id ?? ''}
                onChange={(e) => handleRepoChange(e.target.value)}
                disabled={createSessionMutation.isPending}
                className={`${glassFieldClass} ${glassFieldDefaultClass} min-w-0 flex-1 truncate border-0 bg-transparent py-1.5 pl-1 pr-6 text-sm font-medium sm:max-w-md`}
                aria-label="Select repository for this chat"
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.repo_full_name}
                  </option>
                ))}
              </select>
            )}

            <div className="ml-auto flex shrink-0 items-center gap-1.5">
              <Link
                to="/dashboard/teach"
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[var(--color-text-muted)] hover:bg-white/5 hover:text-[var(--color-cyan)]"
                title="Teach Kassandra"
              >
                Teach
                {gapCount > 0 && (
                  <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--color-warning)]/20 px-1 text-[10px] font-semibold text-[var(--color-warning)]">
                    {gapCount > 99 ? '99+' : gapCount}
                  </span>
                )}
              </Link>
              {projects.length > 0 && (
                <button
                  type="button"
                  onClick={toggleCompareMode}
                  title="Compare repositories"
                  className={`rounded-md px-2 py-1 text-xs ${
                    compareMode
                      ? 'bg-[var(--color-cyan)]/15 text-[var(--color-cyan)]'
                      : 'text-[var(--color-text-muted)] hover:bg-white/5 hover:text-[var(--color-text)]'
                  }`}
                >
                  Compare
                </button>
              )}
              <button
                type="button"
                onClick={toggleSibyl}
                title={
                  sibylEnabled
                    ? 'Sibyl memory is on'
                    : 'Sibyl memory is off — GitHub evidence only'
                }
                className={`rounded-md px-2 py-1 text-xs ${
                  sibylEnabled
                    ? 'bg-[var(--color-cyan)]/15 text-[var(--color-cyan)]'
                    : 'text-[var(--color-text-dim)] line-through hover:bg-white/5'
                }`}
              >
                Sibyl
              </button>
            </div>
          </div>
        </div>

        {isBootstrapping || isSwitchingSession ? (
          <LoadingState
            message={chatLoadingMessage}
            className="flex-1 justify-center px-6"
            size="lg"
          />
        ) : (
          <>
            <div ref={bottomRef} className="flex-1 overflow-y-auto px-6 py-6 lg:px-8">
              <div className="mx-auto max-w-3xl space-y-6">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] px-5 py-3.5 text-sm leading-relaxed whitespace-pre-wrap ${
                        msg.role === 'user'
                          ? 'glass-panel border border-[var(--color-cyan)]/25 bg-gradient-to-r from-[var(--color-cyan)]/12 to-[var(--color-purple)]/8 text-[var(--color-text)]'
                          : 'glass-panel border border-[var(--color-border-subtle)] text-[var(--color-text)]'
                      }`}
                    >
                      {msg.role === 'assistant' && (
                        <p className="mb-2 text-xs font-medium text-[var(--color-cyan)]">Kassandra</p>
                      )}
                      {msg.content}
                      <EvidenceList evidence={msg.evidence} />
                    </div>
                  </div>
                ))}
                {chatMutation.isPending && <ChatTypingIndicator />}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {messages.length <= 1 && (
              <div className="px-6 pb-2 lg:px-8">
                <div className="mx-auto flex max-w-3xl flex-wrap gap-2">
                  {activeSuggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setInput(s)}
                      className="btn-glass btn-glass-chip"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="border-t border-[var(--color-border-subtle)] px-6 py-4 lg:px-8">
              <div className="mx-auto flex max-w-3xl gap-3">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder={
                    compareMode && compareProjectIds.length >= 2
                      ? 'Compare or report across selected repos…'
                      : selectedProject
                        ? `Ask about ${selectedProject.repo_full_name}…`
                        : 'Ask about your project…'
                  }
                  disabled={
                    chatMutation.isPending ||
                    isSwitchingSession ||
                    !sessionId ||
                    !selectedProject ||
                    (compareMode && compareProjectIds.length < 2)
                  }
                  className={`${glassFieldClass} ${glassFieldDefaultClass} flex-1 disabled:opacity-60`}
                />
                <Button
                  onClick={handleSend}
                  disabled={
                    !input.trim() ||
                    isSwitchingSession ||
                    !sessionId ||
                    !selectedProject ||
                    (compareMode && compareProjectIds.length < 2)
                  }
                  loading={chatMutation.isPending}
                  loadingText="Sending…"
                >
                  Send
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
      </div>
    </div>
  )
}

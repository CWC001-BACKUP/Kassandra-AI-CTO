import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { glassFieldClass, glassFieldDefaultClass } from '../../components/ui/surfaceStyles'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { PageHeader } from '../../components/ui/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { LoadingState } from '../../components/ui/LoadingState'
import { authApi, projectsApi } from '../../services/api'
import { useAuth } from '../../context/AuthProvider'
import type { AnalysisResponse } from '../../types'

export function ProjectsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [lastUnderstanding, setLastUnderstanding] = useState<AnalysisResponse | null>(null)

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
  })

  const reposQuery = useQuery({
    queryKey: ['github-repos'],
    queryFn: projectsApi.githubRepos,
    enabled: Boolean(user?.github_username),
    retry: false,
  })

  const addMutation = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['logs'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })

  const activateMutation = useMutation({
    mutationFn: projectsApi.activate,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const removeMutation = useMutation({
    mutationFn: projectsApi.remove,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const analyzeMutation = useMutation({
    mutationFn: projectsApi.analyze,
    onSuccess: (data) => {
      setLastUnderstanding(data)
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['logs'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      void queryClient.invalidateQueries({ queryKey: ['project-understanding'] })
    },
  })

  const projects = projectsQuery.data ?? []
  const projectNames = new Set(projects.map((p) => p.repo_full_name))

  const filteredRepos = (reposQuery.data ?? []).filter((repo) => {
    const q = search.toLowerCase()
    return (
      repo.full_name.toLowerCase().includes(q) ||
      (repo.description?.toLowerCase().includes(q) ?? false)
    )
  })

  const addingRepo = addMutation.isPending ? addMutation.variables?.repo_full_name : null

  return (
    <div className="min-w-0 overflow-x-hidden p-4 sm:p-6 lg:p-8">
      <PageHeader
        title="Projects"
        description="Select GitHub repositories for Kassandra to reconstruct, then interview only on missing WHY"
      />

      {lastUnderstanding?.understanding && (
        <Card className="mb-6 border-[var(--color-cyan)]/25 p-4 sm:p-6">
          <h2 className="text-lg font-semibold">Repository review finished</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--color-text-muted)]">
            {lastUnderstanding.understanding.interview_intro}
          </p>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--color-text-dim)]">
            <span>
              {lastUnderstanding.counts?.observed ??
                lastUnderstanding.understanding.counts?.observed ??
                0}{' '}
              known from the repo
            </span>
            <span>
              {lastUnderstanding.counts?.inferred ??
                lastUnderstanding.understanding.counts?.inferred ??
                0}{' '}
              inferred
            </span>
            <span>
              {lastUnderstanding.understanding.counts?.knowledge_gaps ??
                lastUnderstanding.counts?.knowledge_gaps ??
                0}{' '}
              questions for you
            </span>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/dashboard/teach">
              <Button size="sm">Answer questions</Button>
            </Link>
            <Link to="/dashboard/chat">
              <Button size="sm" variant="outline">
                Open AI Chat
              </Button>
            </Link>
          </div>
        </Card>
      )}

      {!user?.github_username && (
        <Card className="mb-6 border-[var(--color-cyan)]/30 p-4 sm:p-6">
          <h2 className="text-lg font-semibold">Connect GitHub first</h2>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">
            Sign in with GitHub so Kassandra can list your repositories and scope memory per repo.
          </p>
          <Button
            className="mt-4"
            onClick={() => {
              window.location.href = authApi.githubLoginUrl()
            }}
          >
            Connect GitHub
          </Button>
        </Card>
      )}

      {user?.github_username && reposQuery.isError && (
        <Card className="mb-6 border-[var(--color-error)]/30 p-4 sm:p-6">
          <p className="text-sm text-[var(--color-text-muted)]">
            Could not load GitHub repos. You may need to re-authorize with repo access.
          </p>
          <Button
            className="mt-4"
            variant="outline"
            onClick={() => {
              window.location.href = authApi.githubLoginUrl()
            }}
          >
            Re-connect GitHub
          </Button>
        </Card>
      )}

      <div className="grid min-w-0 gap-6 lg:grid-cols-2 lg:gap-8">
        <div className="min-w-0">
          <h2 className="mb-4 text-base font-semibold sm:text-lg">Your projects</h2>
          {projectsQuery.isLoading ? (
            <LoadingState message="Loading projects…" />
          ) : projects.length === 0 ? (
            <Card className="p-4 text-sm text-[var(--color-text-muted)] sm:p-6">
              No projects yet. Add a repository from GitHub below.
            </Card>
          ) : (
            <div className="space-y-3">
              {projects.map((project) => (
                <Card key={project.id} className="p-4">
                  <div className="flex flex-col gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="min-w-0 break-all font-medium leading-snug">
                          {project.repo_full_name}
                        </p>
                        {project.is_active && <Badge variant="cyan">Active</Badge>}
                        {project.language && (
                          <Badge variant="default">{project.language}</Badge>
                        )}
                      </div>
                      {project.description && (
                        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                          {project.description}
                        </p>
                      )}
                      {project.analyzed_at && (
                        <p className="mt-1 text-xs text-[var(--color-text-dim)]">
                          Last analyzed {new Date(project.analyzed_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:justify-end">
                      <Button
                        size="sm"
                        variant="outline"
                        className="min-w-0 w-full sm:w-auto sm:shrink-0"
                        loading={
                          analyzeMutation.isPending &&
                          analyzeMutation.variables === project.id
                        }
                        loadingText="Analyzing…"
                        onClick={() => analyzeMutation.mutate(project.id)}
                      >
                        Analyze
                      </Button>
                      {!project.is_active && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="min-w-0 w-full sm:w-auto sm:shrink-0"
                          loading={
                            activateMutation.isPending &&
                            activateMutation.variables === project.id
                          }
                          loadingText="Setting…"
                          onClick={() => activateMutation.mutate(project.id)}
                        >
                          Set active
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className={`min-w-0 w-full sm:w-auto sm:shrink-0 ${
                          project.is_active ? 'col-span-2 sm:col-span-1' : ''
                        }`}
                        loading={
                          removeMutation.isPending &&
                          removeMutation.variables === project.id
                        }
                        loadingText="Removing…"
                        onClick={() => removeMutation.mutate(project.id)}
                      >
                        Remove
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        <div className="min-w-0">
          <h2 className="mb-4 text-base font-semibold sm:text-lg">Add from GitHub</h2>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search repositories…"
            className={`mb-4 w-full min-w-0 ${glassFieldClass} ${glassFieldDefaultClass}`}
          />

          {reposQuery.isLoading && (
            <LoadingState message="Loading repositories from GitHub…" className="mb-4" />
          )}

          <div className="max-h-[min(28rem,55dvh)] space-y-2 overflow-y-auto sm:max-h-[32rem]">
            {filteredRepos.map((repo) => {
              const added = projectNames.has(repo.full_name)
              const isAdding = addingRepo === repo.full_name
              return (
                <Card key={repo.id} className="p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="break-all font-medium leading-snug">{repo.full_name}</p>
                      <p className="mt-1 text-xs text-[var(--color-text-dim)]">
                        {repo.private ? 'Private' : 'Public'}
                        {repo.language ? ` · ${repo.language}` : ''}
                      </p>
                      {repo.description && (
                        <p className="mt-1 text-sm text-[var(--color-text-muted)] line-clamp-2">
                          {repo.description}
                        </p>
                      )}
                    </div>
                    <Button
                      size="sm"
                      className="w-full shrink-0 sm:w-auto sm:self-start"
                      disabled={added}
                      loading={isAdding}
                      loadingText="Adding…"
                      onClick={() => addMutation.mutate({ repo_full_name: repo.full_name })}
                    >
                      {added ? 'Added' : 'Add'}
                    </Button>
                  </div>
                </Card>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

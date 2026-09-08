import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card } from '../../components/ui/Card'
import { PageHeader } from '../../components/ui/PageHeader'
import { useAuth } from '../../context/AuthProvider'
import { authApi } from '../../services/api'

export function SettingsPage() {
  const { user } = useAuth()

  return (
    <div className="min-w-0 overflow-x-hidden p-4 sm:p-6 lg:p-8">
      <PageHeader
        title="Settings"
        description="Manage your account and integrations"
      />

      <div className="max-w-2xl space-y-6 sm:space-y-8">
        <Card className="p-4 sm:p-6">
          <h2 className="text-base font-semibold sm:text-lg">Profile</h2>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Your account information
          </p>
          <form className="mt-6 space-y-4" onSubmit={(e) => e.preventDefault()}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Full Name" defaultValue={user?.full_name ?? ''} readOnly />
              <Input label="Email" type="email" defaultValue={user?.email ?? ''} readOnly />
            </div>
          </form>
        </Card>

        <Card className="p-4 sm:p-6">
          <h2 className="text-base font-semibold sm:text-lg">Integrations</h2>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Connect external services to your workspace
          </p>
          <div className="mt-6">
            <div className="glass-panel flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 items-start gap-3">
                <svg
                  className="mt-0.5 h-6 w-6 shrink-0"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden
                >
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
                <div className="min-w-0">
                  <p className="text-sm font-medium">GitHub</p>
                  <p className="mt-0.5 text-xs leading-relaxed text-[var(--color-text-dim)]">
                    {user?.github_username
                      ? `Connected as @${user.github_username} — used for repos, changes, and analysis`
                      : 'Not connected — sign in with GitHub to list repos'}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="w-full shrink-0 sm:w-auto"
                onClick={() => {
                  window.location.href = authApi.githubLoginUrl()
                }}
              >
                {user?.github_username ? 'Re-authorize' : 'Connect'}
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

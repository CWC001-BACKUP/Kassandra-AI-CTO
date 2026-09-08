import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card } from '../../components/ui/Card'
import { useAuth, getAuthErrorMessage } from '../../context/AuthProvider'
import { authApi } from '../../services/api'

function GitHubIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  )
}

export function SignupPage() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      const result = await register({ email, password, full_name: fullName })
      navigate('/verify-otp', { state: { email: result.email, devCode: result.devCode } })
    } catch (err) {
      const message = getAuthErrorMessage(err)
      if (message.toLowerCase().includes('not verified')) {
        navigate('/verify-otp', { state: { email } })
        return
      }
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card glow className="p-8">
      <h1 className="text-center font-display text-2xl font-bold">Create your account</h1>
      <p className="mt-2 text-center text-sm text-[var(--color-text-muted)]">
        Start building institutional memory today
      </p>

      {error && (
        <p className="glass-alert mt-4 border-[var(--color-error)]/30 bg-[var(--color-error)]/10 px-4 py-3 text-sm text-[var(--color-error)]">
          {error}
        </p>
      )}

      <Button
        variant="outline"
        fullWidth
        className="mt-8"
        type="button"
        onClick={() => { window.location.href = authApi.githubLoginUrl() }}
      >
        <GitHubIcon />
        Sign up with GitHub
      </Button>

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-[var(--color-border-subtle)]" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="bg-[var(--color-surface-elevated)] px-3 text-[var(--color-text-dim)]">
            or sign up with email
          </span>
        </div>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit}>
        <Input
          label="Full Name"
          type="text"
          placeholder="Jane Doe"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
        />
        <Input
          label="Email"
          type="email"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          label="Password"
          type="password"
          placeholder="Min. 8 characters"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
        />
        <Input
          label="Confirm Password"
          type="password"
          placeholder="••••••••"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
        />
        <Button type="submit" fullWidth loading={loading} loadingText="Creating account…">
          Create Account
        </Button>
      </form>

      <p className="mt-4 text-center text-xs text-[var(--color-text-dim)]">
        By signing up, you agree to our Terms of Service and Privacy Policy.
      </p>

      <p className="mt-4 text-center text-sm text-[var(--color-text-muted)]">
        Already have an account?{' '}
        <Link to="/login" className="text-[var(--color-cyan)] hover:underline">
          Sign in
        </Link>
      </p>
    </Card>
  )
}

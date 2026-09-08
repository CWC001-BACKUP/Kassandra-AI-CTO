import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card } from '../../components/ui/Card'
import { useAuth, getAuthErrorMessage } from '../../context/AuthProvider'

export function ForgotPasswordPage() {
  const navigate = useNavigate()
  const { forgotPassword } = useAuth()
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const devCode = await forgotPassword(email)
      navigate('/verify-otp', {
        state: { email, devCode, mode: 'reset' },
      })
    } catch (err) {
      setError(getAuthErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card glow className="p-8">
      <h1 className="text-center font-display text-2xl font-bold">Reset password</h1>
      <p className="mt-2 text-center text-sm text-[var(--color-text-muted)]">
        Enter your email and we&apos;ll send you a reset code
      </p>

      {error && (
        <p className="glass-alert mt-4 border-[var(--color-error)]/30 bg-[var(--color-error)]/10 px-4 py-3 text-sm text-[var(--color-error)]">
          {error}
        </p>
      )}

      <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
        <Input
          label="Email"
          type="email"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Button type="submit" fullWidth loading={loading} loadingText="Sending…">
          Send Reset Code
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-[var(--color-text-muted)]">
        Remember your password?{' '}
        <Link to="/login" className="text-[var(--color-cyan)] hover:underline">
          Back to sign in
        </Link>
      </p>
    </Card>
  )
}

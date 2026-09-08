import { Link, useLocation, useNavigate } from 'react-router-dom'
import { glassFieldClass, glassFieldDefaultClass } from '../../components/ui/surfaceStyles'
import { useRef, useState, type KeyboardEvent } from 'react'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card } from '../../components/ui/Card'
import { useAuth, getAuthErrorMessage } from '../../context/AuthProvider'

type OtpMode = 'verify' | 'reset'

export function OtpPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { verifyOtp, resendOtp, resetPassword, forgotPassword } = useAuth()
  const state = location.state as {
    email?: string
    devCode?: string
    mode?: OtpMode
    newPassword?: string
  } | null

  const email = state?.email ?? ''
  const mode: OtpMode = state?.mode ?? 'verify'
  const inputs = useRef<(HTMLInputElement | null)[]>([])
  const [code, setCode] = useState(state?.devCode ?? '')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(
    state?.devCode ? `Dev code: ${state.devCode}` : null,
  )
  const [loading, setLoading] = useState(false)

  const handleChange = (index: number, value: string) => {
    const digit = value.replace(/\D/g, '').slice(-1)
    const chars = code.padEnd(6, ' ').split('')
    chars[index] = digit
    const next = chars.join('').trimEnd()
    setCode(next.replace(/\s/g, ''))

    if (digit && index < 5) {
      inputs.current[index + 1]?.focus()
    }
  }

  const handleKeyDown = (index: number, e: KeyboardEvent) => {
    if (e.key === 'Backspace' && !inputs.current[index]?.value && index > 0) {
      inputs.current[index - 1]?.focus()
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email) {
      setError('Missing email. Please start from signup or login.')
      return
    }
    if (code.length !== 6) {
      setError('Please enter the 6-digit code')
      return
    }

    setError(null)
    setLoading(true)
    try {
      if (mode === 'reset') {
        if (!newPassword || newPassword.length < 8) {
          setError('Enter a new password (min. 8 characters)')
          setLoading(false)
          return
        }
        await resetPassword({ email, code, new_password: newPassword })
        navigate('/login', { replace: true })
      } else {
        await verifyOtp(email, code)
        navigate('/dashboard', { replace: true })
      }
    } catch (err) {
      setError(getAuthErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    if (!email) return
    setError(null)
    try {
      const devCode =
        mode === 'reset'
          ? await forgotPassword(email)
          : await resendOtp(email)
      if (devCode) setInfo(`Dev code: ${devCode}`)
    } catch (err) {
      setError(getAuthErrorMessage(err))
    }
  }

  return (
    <Card glow className="p-8">
      <h1 className="text-center font-display text-2xl font-bold">
        {mode === 'reset' ? 'Reset your password' : 'Verify your email'}
      </h1>
      <p className="mt-2 text-center text-sm text-[var(--color-text-muted)]">
        {mode === 'reset'
          ? `Enter the 6-digit code sent to ${email || 'your email'}`
          : 'We sent a 6-digit code to your email. Enter it below.'}
      </p>

      {info && (
        <p className="glass-alert mt-4 border-[var(--color-cyan)]/30 bg-[var(--color-cyan-muted)] px-4 py-3 text-sm text-[var(--color-cyan)]">
          {info}
        </p>
      )}

      {error && (
        <p className="glass-alert mt-4 border-[var(--color-error)]/30 bg-[var(--color-error)]/10 px-4 py-3 text-sm text-[var(--color-error)]">
          {error}
        </p>
      )}

      <form className="mt-8" onSubmit={handleSubmit}>
        <div className="flex justify-center gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <input
              key={i}
              ref={(el) => { inputs.current[i] = el }}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={code[i] ?? ''}
              className={`${glassFieldClass} ${glassFieldDefaultClass} h-12 w-11 px-0 text-center text-lg font-semibold`}
              onChange={(e) => handleChange(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
            />
          ))}
        </div>

        {mode === 'reset' && (
          <div className="mt-6">
            <Input
              label="New Password"
              type="password"
              placeholder="Min. 8 characters"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>
        )}

        <Button
          type="submit"
          fullWidth
          className="mt-8"
          loading={loading}
          loadingText="Verifying…"
        >
          {mode === 'reset' ? 'Reset Password' : 'Verify'}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-[var(--color-text-muted)]">
        Didn&apos;t receive a code?{' '}
        <button
          type="button"
          className="btn-glass-link text-sm"
          onClick={handleResend}
        >
          Resend
        </button>
      </p>

      <p className="mt-2 text-center text-sm text-[var(--color-text-muted)]">
        <Link to="/login" className="text-[var(--color-cyan)] hover:underline">
          Back to sign in
        </Link>
      </p>
    </Card>
  )
}

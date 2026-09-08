import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthProvider'
import { saveSession } from '../../lib/auth-storage'
import { authApi } from '../../services/api'
import type { TokenResponse } from '../../types'

export function GitHubCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { setSessionFromTokens } = useAuth()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const run = async () => {
      const accessToken = searchParams.get('access_token')
      const refreshToken = searchParams.get('refresh_token')
      const expiresIn = searchParams.get('expires_in')
      const refreshExpiresIn = searchParams.get('refresh_expires_in')

      if (!accessToken || !refreshToken) {
        setError('GitHub sign-in failed. Missing tokens.')
        return
      }

      const tokens: TokenResponse = {
        access_token: accessToken,
        refresh_token: refreshToken,
        token_type: 'bearer',
        expires_in: Number(expiresIn ?? 1800),
        refresh_expires_in: Number(refreshExpiresIn ?? 604800),
        user: {
          id: '',
          email: '',
          full_name: '',
          is_verified: true,
        },
      }

      saveSession(tokens)

      try {
        const me = await authApi.me()
        tokens.user = me
        saveSession(tokens)
        setSessionFromTokens(tokens)
        navigate('/dashboard', { replace: true })
      } catch {
        setError('Signed in but failed to load profile.')
      }
    }

    void run()
  }, [navigate, searchParams, setSessionFromTokens])

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)] px-6 text-center">
        <div>
          <p className="text-[var(--color-error)]">{error}</p>
          <button
            type="button"
            onClick={() => navigate('/login')}
            className="btn-glass btn-glass-sm mt-4"
          >
            Back to login
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)]">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-cyan)] border-t-transparent" />
    </div>
  )
}

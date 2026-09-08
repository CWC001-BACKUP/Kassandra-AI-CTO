import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  getStoredSession,
  isAccessTokenExpired,
  saveSession,
  updateSessionUser,
} from '../lib/auth-storage'
import { ApiError, authApi, setAuthFailureHandler } from '../services/api'
import type {
  LoginRequest,
  RegisterRequest,
  ResetPasswordRequest,
  TokenResponse,
  User,
} from '../types'

interface AuthContextValue {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (data: LoginRequest) => Promise<TokenResponse>
  register: (data: RegisterRequest) => Promise<{ email: string; devCode?: string }>
  verifyOtp: (email: string, code: string) => Promise<void>
  resendOtp: (email: string) => Promise<string | undefined>
  logout: () => Promise<void>
  forgotPassword: (email: string) => Promise<string | undefined>
  resetPassword: (data: ResetPasswordRequest) => Promise<void>
  setSessionFromTokens: (tokens: TokenResponse) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

async function ensureFreshSession(): Promise<User | null> {
  const session = getStoredSession()
  if (!session) return null

  if (!isAccessTokenExpired()) {
    return session.user
  }

  try {
    const me = await authApi.me()
    updateSessionUser(me)
    return me
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null
    }
    return getStoredSession()?.user ?? null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    setAuthFailureHandler(() => {
      setUser(null)
    })
    return () => setAuthFailureHandler(null)
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const restored = await ensureFreshSession()
      if (!cancelled) {
        setUser(restored)
        setIsLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (data: LoginRequest) => {
    const tokens = await authApi.login(data)
    setUser(tokens.user)
    return tokens
  }, [])

  const register = useCallback(async (data: RegisterRequest) => {
    const result = await authApi.register(data)
    return {
      email: data.email,
      devCode: result.dev_code ?? undefined,
    }
  }, [])

  const verifyOtp = useCallback(async (email: string, code: string) => {
    const tokens = await authApi.verifyOtp({ email, code })
    setUser(tokens.user)
  }, [])

  const resendOtp = useCallback(async (email: string) => {
    const result = await authApi.resendOtp({ email })
    return result.dev_code ?? undefined
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout()
    setUser(null)
  }, [])

  const forgotPassword = useCallback(async (email: string) => {
    const result = await authApi.forgotPassword({ email })
    return result.dev_code ?? undefined
  }, [])

  const resetPassword = useCallback(async (data: ResetPasswordRequest) => {
    await authApi.resetPassword(data)
  }, [])

  const setSessionFromTokens = useCallback((tokens: TokenResponse) => {
    saveSession(tokens)
    setUser(tokens.user)
  }, [])

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      register,
      verifyOtp,
      resendOtp,
      logout,
      forgotPassword,
      resetPassword,
      setSessionFromTokens,
    }),
    [
      user,
      isLoading,
      login,
      register,
      verifyOtp,
      resendOtp,
      logout,
      forgotPassword,
      resetPassword,
      setSessionFromTokens,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function getAuthErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail ?? error.message
  }
  if (error instanceof Error) return error.message
  return 'Something went wrong'
}

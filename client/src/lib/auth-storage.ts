import type { TokenResponse, User } from '../types'

const STORAGE_KEY = 'kassandra_auth'

export interface StoredSession {
  accessToken: string
  refreshToken: string
  accessExpiresAt: number
  refreshExpiresAt: number
  user: User
}

export function getStoredSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const session = JSON.parse(raw) as StoredSession
    if (Date.now() >= session.refreshExpiresAt) {
      clearStoredSession()
      return null
    }
    return session
  } catch {
    clearStoredSession()
    return null
  }
}

export function saveSession(tokens: TokenResponse): StoredSession {
  const now = Date.now()
  const session: StoredSession = {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    accessExpiresAt: now + tokens.expires_in * 1000,
    refreshExpiresAt: now + tokens.refresh_expires_in * 1000,
    user: tokens.user,
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  return session
}

export function clearStoredSession(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function getAccessToken(): string | null {
  const session = getStoredSession()
  if (!session) return null
  if (Date.now() >= session.accessExpiresAt) return null
  return session.accessToken
}

export function isAccessTokenExpired(): boolean {
  const session = getStoredSession()
  if (!session) return true
  return Date.now() >= session.accessExpiresAt - 30_000
}

export function getRefreshToken(): string | null {
  return getStoredSession()?.refreshToken ?? null
}

export function updateSessionUser(user: User): void {
  const session = getStoredSession()
  if (!session) return
  session.user = user
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

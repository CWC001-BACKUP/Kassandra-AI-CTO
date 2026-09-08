import { API_URL } from '../lib/config'
import {
  clearStoredSession,
  getAccessToken,
  getRefreshToken,
  saveSession,
} from '../lib/auth-storage'
import type {
  ActivityLog,
  AnalysisResponse,
  ChangesResponse,
  ChatRequest,
  ChatResponse,
  ChatSession,
  ChatSessionDetail,
  CreateProjectRequest,
  DashboardActivity,
  DashboardStats,
  ForgotPasswordRequest,
  GenerateReportRequest,
  GitHubRepo,
  LoginRequest,
  MemorySearchResponse,
  MessageResponse,
  Project,
  RegisterRequest,
  Report,
  ResetPasswordRequest,
  TokenResponse,
  User,
  VerifyOtpRequest,
} from '../types'

export class ApiError extends Error {
  status: number
  detail?: string

  constructor(message: string, status: number, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

let refreshPromise: Promise<TokenResponse | null> | null = null

type AuthFailureHandler = () => void
let authFailureHandler: AuthFailureHandler | null = null

export function setAuthFailureHandler(handler: AuthFailureHandler | null): void {
  authFailureHandler = handler
}

function notifyAuthFailure(): void {
  clearStoredSession()
  authFailureHandler?.()
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      return body.detail.map((e: { msg?: string }) => e.msg).join(', ')
    }
  } catch {
    /* ignore */
  }
  return response.statusText
}

async function refreshTokens(): Promise<TokenResponse | null> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    notifyAuthFailure()
    return null
  }

  const response = await fetch(`${API_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })

  if (!response.ok) {
    notifyAuthFailure()
    return null
  }

  const tokens = (await response.json()) as TokenResponse
  saveSession(tokens)
  return tokens
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  retry = true,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  }

  const token = getAccessToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  })

  if (response.status === 401 && retry && path !== '/auth/refresh') {
    if (!refreshPromise) {
      refreshPromise = refreshTokens().finally(() => {
        refreshPromise = null
      })
    }
    const refreshed = await refreshPromise
    if (refreshed) {
      return apiFetch<T>(path, options, false)
    }
    notifyAuthFailure()
  }

  if (!response.ok) {
    if (response.status === 401) {
      notifyAuthFailure()
    }
    const detail = await parseError(response)
    throw new ApiError(`API error: ${response.status}`, response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

function authPost<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export const authApi = {
  register: (data: RegisterRequest) =>
    authPost<MessageResponse>('/auth/register', data),

  verifyOtp: async (data: VerifyOtpRequest) => {
    const tokens = await authPost<TokenResponse>('/auth/verify-otp', data)
    saveSession(tokens)
    return tokens
  },

  resendOtp: (data: { email: string }) =>
    authPost<MessageResponse>('/auth/resend-otp', data),

  login: async (data: LoginRequest) => {
    const tokens = await authPost<TokenResponse>('/auth/login', data)
    saveSession(tokens)
    return tokens
  },

  logout: async () => {
    const refreshToken = getRefreshToken()
    if (refreshToken) {
      try {
        await authPost<MessageResponse>('/auth/logout', {
          refresh_token: refreshToken,
        })
      } catch {
        /* clear locally even if server call fails */
      }
    }
    clearStoredSession()
  },

  me: () => apiFetch<User>('/auth/me'),

  forgotPassword: (data: ForgotPasswordRequest) =>
    authPost<MessageResponse>('/auth/forgot-password', data),

  resetPassword: (data: ResetPasswordRequest) =>
    authPost<MessageResponse>('/auth/reset-password', data),

  githubLoginUrl: () => `${API_URL}/auth/github`,
}

export const chatApi = {
  send: (data: ChatRequest) => apiFetch<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  listSessions: () => apiFetch<ChatSession[]>('/chat/sessions'),

  createSession: (projectId?: string | null) =>
    apiFetch<ChatSessionDetail>('/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId ?? null }),
    }),

  getSession: (sessionId: string) =>
    apiFetch<ChatSessionDetail>(`/chat/sessions/${sessionId}`),

  deleteSession: (sessionId: string) =>
    apiFetch<void>(`/chat/sessions/${sessionId}`, { method: 'DELETE' }),
}

export const projectsApi = {
  list: () => apiFetch<Project[]>('/projects'),

  create: (data: CreateProjectRequest) =>
    apiFetch<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  activate: (projectId: string) =>
    apiFetch<Project>(`/projects/${projectId}/activate`, { method: 'POST' }),

  remove: (projectId: string) =>
    apiFetch<void>(`/projects/${projectId}`, { method: 'DELETE' }),

  githubRepos: () => apiFetch<GitHubRepo[]>('/github/repos'),

  searchMemory: (q: string) =>
    apiFetch<MemorySearchResponse>(`/memory/search?q=${encodeURIComponent(q)}`),

  analyze: (projectId: string) =>
    apiFetch<AnalysisResponse>(`/projects/${projectId}/analyze`, { method: 'POST' }),
}

export const changesApi = {
  list: (projectId?: string) =>
    apiFetch<ChangesResponse>(
      `/changes${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`,
    ),
}

export const logsApi = {
  list: (params?: { level?: string; search?: string }) => {
    const qs = new URLSearchParams()
    if (params?.level) qs.set('level', params.level)
    if (params?.search) qs.set('search', params.search)
    const query = qs.toString()
    return apiFetch<ActivityLog[]>(`/logs${query ? `?${query}` : ''}`)
  },
}

export const reportsApi = {
  list: () => apiFetch<Report[]>('/reports'),

  get: (id: string) => apiFetch<Report>(`/reports/${id}`),

  generate: (data: GenerateReportRequest) =>
    apiFetch<Report>('/reports/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

export const dashboardApi = {
  stats: () => apiFetch<DashboardStats>('/dashboard/stats'),
  activity: () => apiFetch<DashboardActivity[]>('/dashboard/activity'),
}

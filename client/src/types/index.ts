export interface User {
  id: string
  email: string
  full_name: string
  is_verified: boolean
  github_username?: string | null
  avatar_url?: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  refresh_expires_in: number
  user: User
}

export interface MessageResponse {
  message: string
  requires_verification?: boolean
  dev_code?: string | null
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
}

export interface VerifyOtpRequest {
  email: string
  code: string
}

export interface ForgotPasswordRequest {
  email: string
}

export interface ResetPasswordRequest {
  email: string
  code: string
  new_password: string
}

export interface HealthResponse {
  status: string
  sibyl?: {
    ready: boolean
    data_dir: string
    credentials_present: boolean
    error: string | null
  }
}

export interface EvidenceRef {
  label: string
  url?: string | null
  source?: 'github' | 'sibyl' | 'session'
  kind?: string | null
}

export interface ChatRequest {
  message: string
  project_id?: string | null
  project_ids?: string[] | null
  session_id?: string | null
  sibyl_enabled?: boolean
}

export interface ChatResponse {
  reply: string
  source: string
  intent?: string | null
  project_id?: string | null
  session_id?: string | null
  memory_hits: number
  evidence?: EvidenceRef[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  source?: string | null
  evidence?: EvidenceRef[]
  created_at: string
}

export interface ChatSession {
  id: string
  title: string
  project_id?: string | null
  created_at: string
  updated_at: string
  message_count: number
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[]
}

export interface GitHubRepo {
  id: number
  full_name: string
  name: string
  owner: string
  html_url: string
  description?: string | null
  private: boolean
  default_branch: string
  language?: string | null
  updated_at?: string | null
}

export interface Project {
  id: string
  repo_full_name: string
  repo_url: string
  description?: string | null
  default_branch: string
  language?: string | null
  is_active: boolean
  analyzed_at?: string | null
  created_at: string
}

export interface CreateProjectRequest {
  repo_full_name: string
}

export interface MemorySearchResponse {
  query: string
  tenant_id: string
  results: Array<Record<string, unknown>>
  count: number
}

export interface ChangeItem {
  id: string | number
  type: 'pr' | 'commit' | string
  title: string
  author: string
  branch: string
  status: string
  files: number
  additions: number
  deletions: number
  html_url?: string | null
  time: string
  number?: number | null
}

export interface ChangesResponse {
  changes: ChangeItem[]
  stats: {
    this_week: number
    open_prs: number
    total_additions: number
    total_deletions: number
  }
  repo_full_name?: string | null
}

export interface ActivityLog {
  id: string
  level: string
  source: string
  message: string
  project_id?: string | null
  metadata?: Record<string, unknown> | null
  timestamp: string
}

export interface Report {
  id: string
  report_type: string
  title: string
  content: string
  status: string
  project_id?: string | null
  created_at: string
}

export interface GenerateReportRequest {
  report_type: 'sprint' | 'incident' | 'architecture' | 'onboarding'
  project_id?: string | null
}

export interface AnalysisResponse {
  repo_full_name: string
  analyzed_at: string
  languages: Record<string, number>
  root_files: string[]
  config_files: string[]
  readme_found: boolean
  webhook_registered: boolean
  understanding?: ProjectUnderstanding | null
  counts?: Record<string, number> | null
  history_meta?: Record<string, unknown> | null
}

export interface MemoryCard {
  memory_id?: string | null
  sibyl_key?: string | null
  type?: string | null
  title?: string | null
  content?: string | null
  decision?: string | null
  reason?: string | null
  outcome?: string | null
  alternatives?: string[]
  confidence?: string | null
  source?: string | null
  source_reference?: string | null
  status?: string | null
  priority?: string | null
  question?: string | null
  affected_components?: string[]
  tags?: string[]
  historical_date?: string | null
  related_commits?: string[]
  related_prs?: string[]
  updated_at?: string | null
  confirmed_at?: string | null
}

export interface ProjectUnderstanding {
  repo_full_name: string
  headline: string
  architecture: MemoryCard[]
  historical_evolution: MemoryCard[]
  problems?: MemoryCard[]
  inferred?: MemoryCard[]
  confirmed?: MemoryCard[]
  reviewable_facts?: MemoryCard[]
  counts: {
    observed?: number
    inferred?: number
    confirmed?: number
    knowledge_gaps?: number
    high_priority_gaps?: number
    problems?: number
    reviewable?: number
    stored?: number
  }
  knowledge_gaps: Array<{
    memory_id?: string | null
    question: string
    priority?: string | null
    affected_components?: string[]
    reason?: string | null
  }>
  confidence_areas: Record<string, string>
  interview_intro: string
  updated_at?: string | null
}

export interface MemoryReviewResponse {
  ok: boolean
  action?: string | null
  reason?: string | null
  memory?: MemoryCard | null
  correction?: MemoryCard | null
}

export interface TeachResponse {
  stored: boolean
  awaiting_confirmation?: boolean
  reason?: string | null
  memory?: Record<string, unknown> | null
  memories?: Array<Record<string, unknown>>
  pending?: {
    pending_id?: string
    candidate_count?: number
    candidates?: Array<{
      index?: number
      title?: string | null
      decision?: string | null
      reason?: string | null
      content?: string | null
      type?: string | null
      confidence?: string | null
      status?: string | null
    }>
  } | null
  conflicts: Array<Record<string, unknown>>
  duplicate?: boolean
  gap_resolved?: boolean
  gaps_removed?: number
  reply?: string | null
  verified?: boolean
  selected_count?: number | null
  discarded_count?: number | null
}

export interface DashboardStats {
  projects_count: number
  active_project?: string | null
  memory_count: number
  knowledge_gap_count?: number
  changes_today: number
  reports_count: number
}

export interface DashboardActivity {
  type: string
  message: string
  time: string
}

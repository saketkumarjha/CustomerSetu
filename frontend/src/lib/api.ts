/**
 * API client — all calls to the FastAPI backend go through here.
 * Dev: Vite proxy forwards /api/* → http://localhost:8000 (vite.config.ts)
 * Prod: VITE_API_BASE_URL points directly to the Railway/Render backend URL
 */

const API_KEY = (import.meta.env.VITE_API_KEY as string) || 'sk_my_super_secret_key_123'
// Empty string in dev (proxy handles it). Full URL in prod e.g. https://xxx.railway.app
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || ''

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return { 'X-API-Key': API_KEY, ...extra }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { detail = (await res.json()).detail ?? detail } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { headers: authHeaders() })
  return handleResponse<T>(res)
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  extra: Record<string, string> = {},
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json', ...extra }),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  return handleResponse<T>(res)
}

export async function apiPostForm<T>(
  path: string,
  formData: FormData,
  extra: Record<string, string> = {},
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: authHeaders(extra),
    body: formData,
  })
  return handleResponse<T>(res)
}

/** EventSource for SSE — passes API key as query param (backend auth.py supports this) */
export function createPipelineStream(complaintId: string): EventSource {
  return new EventSource(`${BASE_URL}/api/v1/pipeline/stream/${complaintId}?api_key=${encodeURIComponent(API_KEY)}`)
}

// ── Typed endpoint helpers ────────────────────────────────────────────────────

export const api = {
  complaints: {
    submit: (form: FormData, idempotencyKey: string) =>
      apiPostForm<SubmitResponse>('/api/v1/complaints/submit', form, {
        'X-Idempotency-Key': idempotencyKey,
      }),
    list: (params?: { route?: string; category?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams()
      if (params?.route) qs.set('route', params.route)
      if (params?.category) qs.set('category', params.category)
      qs.set('limit', String(params?.limit ?? 50))
      qs.set('offset', String(params?.offset ?? 0))
      return apiGet<ComplaintsListResponse>(`/api/v1/complaints/?${qs}`)
    },
    get: (id: string) => apiGet<ApiComplaint>(`/api/v1/complaints/${id}`),
    explanation: (id: string) => apiGet<ExplanationResponse>(`/api/v1/complaints/${id}/explanation`),
    shadowOverride: (id: string, body: { agent_id: string; corrected_response: string; override_reason: string }) =>
      apiPost(`/api/v1/complaints/${id}/shadow-override`, body),
  },
  pipeline: {
    run: (complaintId: string) =>
      apiPost<PipelineRunResponse>(`/api/v1/pipeline/run/${complaintId}`),
  },
  dashboard: {
    stats: (days = 30) => apiGet<DashboardStats>(`/api/v1/dashboard/stats?days=${days}`),
    csatTrends: (days = 30) => apiGet<CSATTrends>(`/api/v1/dashboard/csat-trends?days=${days}`),
    pipelineHealth: (days = 7) => apiGet<PipelineHealth>(`/api/v1/dashboard/pipeline-health?days=${days}`),
  },
  feedback: {
    submitAgent: (body: AgentFeedbackBody) => apiPost('/api/v1/feedback/agent', body),
    datasetStats: () => apiGet<DatasetStats>('/api/v1/feedback/dataset-stats'),
  },
  rbi: {
    report: () => apiGet<RBIReport>('/api/v1/rbi/report'),
    pending: (hrs = 24) => apiGet<RBIPending>(`/api/v1/rbi/pending?hours_threshold=${hrs}`),
    categories: () => apiGet<RBICategories>('/api/v1/rbi/categories'),
    log: (id: string) => apiPost(`/api/v1/rbi/log/${id}`),
  },
  sla: {
    summary: () => apiGet<SLASummary>('/api/v1/sla/summary'),
    atRisk: () => apiGet<SLAAtRisk>('/api/v1/sla/at-risk'),
  },
}

// ── Backend API response types ────────────────────────────────────────────────

export interface SubmitResponse {
  complaint_id: string
  complaint_text: string
  channel: string
  has_image: boolean
  image_url?: string | null
  extraction_method?: string | null
  extracted_image_text?: string | null
  merged_text: string
  status: string
  message: string
}

export interface PipelineRunResponse {
  message: string
  complaint_id: string
  stream_url?: string
  current_status?: string
  final_route?: string
  category?: string
  severity?: number
  route?: string
}

export interface ApiComplaint {
  complaint_id: string
  customer_id: string
  channel: string
  original_text?: string
  merged_text?: string
  masked_text?: string
  language?: string
  category?: string
  category_confidence?: number
  sentiment?: string
  urgency_score?: number
  escalation_flag?: boolean
  compliance_category?: string
  is_rbi_reportable?: boolean
  rbi_supervisor_override?: boolean
  severity?: number
  severity_score?: number
  draft_response?: string
  root_cause?: string
  action_steps?: string[]
  confidence_score?: number
  grounding_score?: number
  grounding_warnings?: string[]
  route?: string
  risk_score?: number
  sla_hours?: number
  rbi_tat_deadline?: string
  pipeline_status?: string
  status?: string
  image_url?: string
  extraction_method?: string
  is_duplicate?: boolean
  duplicate_of?: string
  duplicate_similarity?: number
  created_at?: string
}

export interface ComplaintsListResponse {
  total: number
  limit: number
  offset: number
  complaints: ApiComplaint[]
}

export interface AgentDecision {
  agent_name: string
  agent_order: number
  status: string
  decision?: string
  confidence?: number
  reasoning?: string
  evidence?: string[]
  duration_ms?: number
  metadata?: Record<string, unknown>
  error_message?: string
}

export interface ExplanationResponse {
  complaint_id: string
  pipeline_status: string
  final_route?: string
  category?: string
  severity?: number
  total_agents: number
  explanation_trace: AgentDecision[]
}

export interface DashboardStats {
  period_days: number
  generated_at: string
  overview: {
    total_complaints: number
    auto_responded: number
    human_review: number
    pending_pipeline: number
    auto_respond_rate_percent: number
    rbi_reportable: number
    rbi_reportable_rate_percent: number
    closed: number
    open: number
  }
  averages: { avg_severity: number; avg_confidence_score: number; avg_risk_score: number }
  distributions: {
    by_category: Array<{ category: string; count: number; percent: number }>
    by_sentiment: Array<{ sentiment: string; count: number; percent: number }>
    by_severity: Array<{ severity: number; label: string; count: number; percent: number }>
    by_channel: Array<{ channel: string; count: number; percent: number }>
  }
  daily_volume: Array<{ date: string; count: number }>
}

export interface CSATTrends {
  period_days: number
  overall?: { total_responses: number; average_csat: number; csat_label: string }
  by_category?: Array<{ category: string; avg_csat: number; response_count: number }>
  by_channel?: Array<{ channel: string; avg_csat: number; response_count: number }>
  weekly_trend?: Array<{ week: string; avg_csat: number | null; response_count: number }>
  message?: string
}

export interface PipelineHealth {
  period_days: number
  summary?: {
    total_agent_executions: number
    overall_success_rate: number
    total_failures: number
  }
  per_agent?: Array<{
    agent_name: string
    agent_order: number
    total_runs: number
    success_rate: number
    failure_count: number
    avg_duration_ms: number
  }>
  message?: string
}

export interface AgentFeedbackBody {
  complaint_id: string
  agent_id: string
  action: 'accept' | 'edit' | 'reject' | 'escalate'
  original_draft: string
  final_response?: string
  rejection_reason?: string
}

export interface DatasetStats {
  total_records: number
  by_category?: Record<string, number>
  fine_tuning_readiness?: { current: number; recommended_minimum: number; percentage: number; status: string }
}

export interface RBIReport {
  report_metadata: { generated_at: string; report_type: string }
  summary: {
    total_complaints: number
    rbi_reportable_complaints: number
    tat_compliance_rate_percent: number
    tat_breached_count: number
    human_review_count: number
    auto_respond_count: number
    auto_respond_rate_percent: number
  }
  rbi_category_breakdown: Array<{
    rbi_category: string
    display_label: string
    total_count: number
    human_review_count: number
    resolved_count: number
    tat_breached_count: number
  }>
  compliance_status: string
  compliance_notes: string[]
}

export interface RBIPending {
  generated_at: string
  summary: { total_pending_rbi: number; breached_count: number; warning_count: number; safe_count: number }
  breached: Array<{ complaint_id: string; compliance_category: string; hours_remaining: number; deadline_readable: string; category: string; alert_level: string }>
  approaching_breach: Array<{ complaint_id: string; compliance_category: string; hours_remaining: number; deadline_readable: string; category: string; alert_level: string }>
}

export interface RBICategories {
  total_categories: number
  categories: Array<{
    category_code: string
    display_label: string
    is_rbi_reportable: boolean
    supervisor_override_always_human: boolean
    sla_label: string
    resolution_hours: number
    penalty_per_day: number
    penalty_description: string
  }>
}

export interface SLASummary {
  generated_at: string
  overall_health: string
  open_complaints: number
  human_review_queue: number
  rbi_tat_breached: number
  rbi_tat_at_risk_24h: number
  predicted_breach: { critical: number; high: number; total_at_risk: number }
  action_required: boolean
}

export interface SLAAtRisk {
  generated_at: string
  total_open_complaints: number
  at_risk_count: number
  risk_summary: Record<string, number>
  system_alert?: string | null
  predictions: Array<{
    complaint_id: string
    breach_probability: number
    risk_level: string
    estimated_breach_in_hours?: number
    category?: string
    severity?: number
    is_rbi_reportable?: boolean
  }>
}

// ── Navigation ────────────────────────────────────────────────────────────────
export type TabId =
  | 'overview'
  | 'complaints'
  | 'agentDesk'
  | 'submit'
  | 'pipeline'
  | 'analytics'
  | 'feedback'
  | 'rbi'
  | 'sla'

// ── Frontend display types (also used for mock data) ─────────────────────────
export type Severity = 'Critical' | 'High' | 'Medium' | 'Low'
export type Status = 'Open' | 'In Progress' | 'Pending' | 'Resolved' | 'Escalated'
export type Sentiment =
  | 'Angry' | 'Furious' | 'Frustrated' | 'Upset' | 'Stressed'
  | 'Anxious' | 'Confused' | 'Concerned' | 'Neutral' | 'Satisfied'
export type Channel = 'Email' | 'Phone' | 'Web Form' | 'Mobile App' | 'Social Media'
export type ComplianceRisk = 'HIGH' | 'MEDIUM' | 'LOW'

// ── Helpers: map backend values → frontend display types ────────────────────
export function severityFromInt(n: number | null | undefined): Severity {
  if (!n || n <= 1) return 'Low'
  if (n === 2) return 'Medium'
  if (n === 3) return 'High'
  return 'Critical'
}

export function statusFromApi(status?: string, route?: string): Status {
  if (!status) return 'Open'
  if (status === 'closed' || status === 'resolved' || status === 'awaiting_feedback') return 'Resolved'
  if (status === 'auto_respond' || route === 'auto_respond') return 'Resolved'
  if (status === 'human_review' || route === 'human_review') return 'In Progress'
  if (status === 'processing') return 'In Progress'
  if (status === 'failed') return 'Escalated'
  if (status === 'complete') return 'Resolved'
  if (status === 'pending') return 'Pending'
  return 'Open'
}

export function slaLabel(slaHours?: number | null, createdAt?: string | null, tatDeadline?: string | null): string {
  if (tatDeadline) {
    const remaining = (new Date(tatDeadline).getTime() - Date.now()) / 3600000
    if (remaining < 0) return 'BREACHED'
    if (remaining < 1) return `${Math.round(remaining * 60)}m left`
    return `${Math.round(remaining)}h left`
  }
  if (slaHours && createdAt) {
    const deadline = new Date(createdAt).getTime() + slaHours * 3600000
    const remaining = (deadline - Date.now()) / 3600000
    if (remaining < 0) return 'BREACHED'
    if (remaining < 1) return `${Math.round(remaining * 60)}m left`
    return `${Math.round(remaining)}h left`
  }
  return slaHours ? `${slaHours}h SLA` : '—'
}

export function isSlaBreached(slaHours?: number | null, createdAt?: string | null, tatDeadline?: string | null): boolean {
  if (tatDeadline) return new Date(tatDeadline).getTime() < Date.now()
  if (slaHours && createdAt) {
    return new Date(createdAt).getTime() + slaHours * 3600000 < Date.now()
  }
  return false
}

// ── Existing frontend Complaint model (used by mock data) ────────────────────
export interface HistoryEntry {
  time: string
  actor: string
  action: string
}

export interface ClassificationResult {
  category: string
  product: string
  severity: Severity
  type: string
  confidence: number
}

export interface SentimentResult {
  emotion: Sentiment
  urgency: number
  score: number
  escalate: boolean
  confidence: number
}

export interface DuplicateResult {
  isDuplicate: boolean
  similar: number
  confidence: number
}

export interface ComplianceResult {
  flagged: boolean
  risk: ComplianceRisk
  reason: string
  confidence: number
}

export interface AgentResult {
  classification: ClassificationResult
  sentiment: SentimentResult
  duplicate: DuplicateResult
  compliance: ComplianceResult
  resolution: string
}

export interface Complaint {
  id: string
  customer: string
  accountNo: string
  phone: string
  channel: Channel
  category: string
  type: string
  severity: Severity
  sentiment: Sentiment
  sentimentScore: number
  status: Status
  slaHours: number
  slaRemaining: string
  slaBreached: boolean
  assignee: string
  branch: string
  date: string
  time: string
  description: string
  history: HistoryEntry[]
  agentResult: AgentResult
}

// ── Analytics chart types ─────────────────────────────────────────────────────
export interface TrendDataPoint {
  month: string
  total: number
  resolved: number
  critical: number
}

export interface CategoryDataPoint {
  name: string
  count: number
}

export interface SentimentDataPoint {
  name: string
  value: number
}

export interface SlaDataPoint {
  month: string
  met: number
  breached: number
}

// ── Live SSE pipeline event ───────────────────────────────────────────────────
export interface PipelineSSEEvent {
  event: string
  agent?: string
  order?: number
  status?: 'processing' | 'complete' | 'failed'
  decision?: string
  confidence?: number
  reasoning?: string
  evidence?: string[]
  duration_ms?: number
  complaint_id?: string
  route?: string
  category?: string
  severity?: number
  error?: string
}

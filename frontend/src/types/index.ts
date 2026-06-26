// ── Navigation ────────────────────────────────────────────────────────────────
export type TabId =
  | "overview"
  | "complaints"
  | "pipeline"
  | "agent"
  | "analytics"
  | "analytics-overview"
  | "analytics-ai-performance"
  | "analytics-customer-feedback"
  | "analytics-root-cause"
  | "rbi"
  | "sla"
  | "kb"
  | "customers";

// ── 360° Customer View types ──────────────────────────────────────────────────
export interface CustomerCard {
  cif_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  account_number: string | null;
  verified: boolean;
  customer_since: string | null;
  total_complaints: number;
  active_complaints: number;
  resolved_complaints: number;
  merged_complaints: number;
  last_complaint_date: string | null;
  last_complaint_status: string | null;
}

export interface CustomerListResponse {
  total: number;
  page: number;
  page_size: number;
  customers: CustomerCard[];
}

export interface CustomerSummary {
  cif_id: string;
  summary_text: string | null;
  complaint_count: number;
  last_updated: string | null;
}

export interface CustomerDetail {
  profile: {
    cif_id: string;
    name: string;
    email: string | null;
    phone: string | null;
    account_number: string | null;
    verified: boolean;
    customer_since: string | null;
  };
  stats: {
    total_complaints: number;
    active_complaints: number;
    resolved_complaints: number;
    merged_complaints: number;
    last_complaint_date: string | null;
    last_complaint_status: string | null;
    avg_resolution_days: number | null;
  };
  complaints: Record<string, unknown>[];
  category_breakdown: { category: string; count: number }[];
  sentiment_trend: { date: string; sentiment: string; complaint_id: string }[];
  timeline_events: { event: string; complaint_id?: string; channel?: string; tier?: number; timestamp?: string }[];
  replies: { complaint_id: string; channel?: string; reply: string; route?: string; timestamp?: string }[];
  followups: { complaint_id: string; duplicate_of?: string; channel?: string; category?: string; timestamp?: string; status?: string }[];
  notes: { complaint_id: string; type: string; content: unknown; timestamp?: string }[];
  insights: string[];
}

// ── Frontend display types (also used for mock data) ─────────────────────────
export type Severity = "Critical" | "High" | "Medium" | "Low";
export type Status =
  | "Open"
  | "In Progress"
  | "Pending"
  | "Resolved"
  | "Escalated";
export type Sentiment =
  | "Angry"
  | "Furious"
  | "Frustrated"
  | "Upset"
  | "Stressed"
  | "Anxious"
  | "Confused"
  | "Concerned"
  | "Neutral"
  | "Satisfied";
export type Channel =
  | "Email"
  | "Phone"
  | "Web Form"
  | "Mobile App"
  | "Social Media";
export type ComplianceRisk = "HIGH" | "MEDIUM" | "LOW";

// ── Helpers: map backend values → frontend display types ────────────────────
export function severityFromInt(n: number | null | undefined): Severity {
  if (!n || n <= 1) return "Low";
  if (n === 2) return "Medium";
  if (n === 3) return "High";
  return "Critical";
}

export function statusFromApi(status?: string, route?: string): Status {
  if (!status) return "Open";
  // Resolved states
  if (
    status === "closed" ||
    status === "resolved" ||
    status === "awaiting_feedback" ||
    status === "auto_closed"
  )
    return "Resolved";
  if (status === "auto_respond" || route === "auto_respond") return "Resolved";
  // In-progress / human review states
  if (
    status === "human_review" ||
    status === "pending_review" ||
    status === "in_review" ||
    status === "review_started" ||
    route === "human_review" ||
    route === "HUMAN"
  )
    return "In Progress";
  if (status === "processing" || status === "started") return "In Progress";
  // Escalated
  if (status === "failed" || status === "escalated") return "Escalated";
  // Pending
  if (status === "pending") return "Pending";
  // Complete pipeline but no specific route
  if (status === "complete") return "Resolved";
  return "Open";
}

export function slaLabel(
  slaHours?: number | null,
  createdAt?: string | null,
  tatDeadline?: string | null,
): string {
  // Use RBI TAT deadline if available (most precise)
  if (tatDeadline) {
    const remaining = (new Date(tatDeadline).getTime() - Date.now()) / 3600000;
    if (remaining < 0) return "Breached";
    if (remaining < 1) return `${Math.round(remaining * 60)}m left`;
    if (remaining < 48) return `${Math.round(remaining)}h left`;
    return `${Math.round(remaining / 24)}d left`;
  }
  // Use sla_hours + created_at if set by pipeline
  if (slaHours && createdAt) {
    const deadline = new Date(createdAt).getTime() + slaHours * 3600000;
    const remaining = (deadline - Date.now()) / 3600000;
    if (remaining < 0) return "Breached";
    if (remaining < 1) return `${Math.round(remaining * 60)}m left`;
    if (remaining < 48) return `${Math.round(remaining)}h left`;
    return `${Math.round(remaining / 24)}d left`;
  }
  // Fallback: use created_at + 30-day RBI default when pipeline hasn't set SLA yet
  if (createdAt) {
    const DEFAULT_SLA_HOURS = 720; // 30 days — RBI general complaint mandate
    const deadline =
      new Date(createdAt).getTime() + DEFAULT_SLA_HOURS * 3600000;
    const remaining = (deadline - Date.now()) / 3600000;
    if (remaining < 0) return "Breached";
    if (remaining < 1) return `${Math.round(remaining * 60)}m left`;
    if (remaining < 48) return `${Math.round(remaining)}h left`;
    return `${Math.round(remaining / 24)}d left`;
  }
  return "—";
}

export function isSlaBreached(
  slaHours?: number | null,
  createdAt?: string | null,
  tatDeadline?: string | null,
): boolean {
  if (tatDeadline) return new Date(tatDeadline).getTime() < Date.now();
  if (slaHours && createdAt) {
    return new Date(createdAt).getTime() + slaHours * 3600000 < Date.now();
  }
  // Fallback: 30-day default
  if (createdAt) {
    return new Date(createdAt).getTime() + 720 * 3600000 < Date.now();
  }
  return false;
}

// ── Existing frontend Complaint model (used by mock data) ────────────────────
export interface HistoryEntry {
  time: string;
  actor: string;
  action: string;
}

export interface ClassificationResult {
  category: string;
  product: string;
  severity: Severity;
  type: string;
  confidence: number;
}

export interface SentimentResult {
  emotion: Sentiment;
  urgency: number;
  score: number;
  escalate: boolean;
  confidence: number;
}

export interface DuplicateResult {
  isDuplicate: boolean;
  similar: number;
  confidence: number;
}

export interface ComplianceResult {
  flagged: boolean;
  risk: ComplianceRisk;
  reason: string;
  confidence: number;
}

export interface AgentResult {
  classification: ClassificationResult;
  sentiment: SentimentResult;
  duplicate: DuplicateResult;
  compliance: ComplianceResult;
  resolution: string;
}

export interface Complaint {
  id: string;
  customer: string;
  accountNo: string;
  phone: string;
  channel: Channel;
  category: string;
  type: string;
  severity: Severity;
  sentiment: Sentiment;
  sentimentScore: number;
  status: Status;
  slaHours: number;
  slaRemaining: string;
  slaBreached: boolean;
  assignee: string;
  branch: string;
  date: string;
  time: string;
  description: string;
  history: HistoryEntry[];
  agentResult: AgentResult;
  duplicateStatus?: 'possible_duplicate' | 'confirmed_duplicate' | 'merged';
  duplicateOf?: string[];
  mergedInto?: string;
}

// ── Analytics chart types ─────────────────────────────────────────────────────
export interface TrendDataPoint {
  month: string;
  total: number;
  resolved: number;
  critical: number;
}

export interface CategoryDataPoint {
  name: string;
  count: number;
}

export interface SentimentDataPoint {
  name: string;
  value: number;
}

export interface SlaDataPoint {
  month: string;
  met: number;
  breached: number;
}

// ── Live SSE pipeline event ───────────────────────────────────────────────────
export interface PipelineSSEEvent {
  event: string;
  agent?: string;
  order?: number;
  status?: "processing" | "complete" | "failed";
  decision?: string;
  confidence?: number;
  reasoning?: string;
  evidence?: string[];
  duration_ms?: number;
  complaint_id?: string;
  route?: string;
  category?: string;
  severity?: number;
  error?: string;
}

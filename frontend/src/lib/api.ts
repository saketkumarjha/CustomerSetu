/**
 * API client — all calls to the FastAPI backend go through here.
 * Dev: Vite proxy forwards /api/* → http://localhost:8000 (vite.config.ts)
 * Prod: VITE_API_BASE_URL points directly to the Railway/Render backend URL
 */

const API_KEY =
  (import.meta.env.VITE_API_KEY as string) || "sk_my_super_secret_key_123";
// Empty string in dev (proxy handles it). Full URL in prod e.g. https://xxx.railway.app
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || "";

function authHeaders(
  extra: Record<string, string> = {},
): Record<string, string> {
  return { "X-API-Key": API_KEY, ...extra };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { headers: authHeaders() });
  return handleResponse<T>(res);
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  extra: Record<string, string> = {},
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json", ...extra }),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res);
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res);
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
}

export async function apiPostForm<T>(
  path: string,
  formData: FormData,
  extra: Record<string, string> = {},
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: authHeaders(extra),
    body: formData,
  });
  return handleResponse<T>(res);
}

/** EventSource for SSE — passes API key as query param (backend auth.py supports this) */
export function createPipelineStream(complaintId: string): EventSource {
  return new EventSource(
    `${BASE_URL}/api/v1/pipeline/stream/${complaintId}?api_key=${encodeURIComponent(API_KEY)}`,
  );
}

export interface ExportDatasetQuery {
  minCombinedScore?: number;
  category?: string;
  onlyAgentAccepted?: boolean;
  preview?: boolean;
}

function buildExportDatasetSearchParams(params?: ExportDatasetQuery): string {
  const qs = new URLSearchParams();
  if (params?.minCombinedScore != null && params.minCombinedScore > 0) {
    qs.set("min_combined_score", String(params.minCombinedScore));
  }
  if (params?.category?.trim()) qs.set("category", params.category.trim());
  if (params?.onlyAgentAccepted) qs.set("only_agent_accepted", "true");
  if (params?.preview) qs.set("preview", "true");
  return qs.toString();
}

export type DatasetExportDownloadResult =
  | { message: string; total_records?: number; hint?: string }
  | { downloaded: true; filename: string; recordCount?: number };

async function downloadFineTuneDatasetFile(
  params?: Omit<ExportDatasetQuery, "preview">,
): Promise<DatasetExportDownloadResult> {
  const qs = buildExportDatasetSearchParams({ ...params, preview: false });
  const path = `/api/v1/feedback/export-dataset${qs ? `?${qs}` : ""}`;
  const res = await fetch(`${BASE_URL}${path}`, { headers: authHeaders() });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = (await res.json()) as { detail?: string; message?: string };
      detail = j.detail ?? j.message ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return (await res.json()) as DatasetExportDownloadResult;
  }
  const blob = await res.blob();
  let filename = "fine_tune_dataset.jsonl";
  const cd = res.headers.get("Content-Disposition");
  const m = cd?.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)/i);
  if (m) filename = decodeURIComponent(m[1].trim());
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  const totalHeader = res.headers.get("X-Total-Records");
  return {
    downloaded: true as const,
    filename,
    recordCount: totalHeader ? parseInt(totalHeader, 10) : undefined,
  };
}

// ── Agent desk (staff queue & metrics) types ──────────────────────────────────

export interface AgentQueueItem {
  id: string;
  queue_status?: string;
  assigned_to?: string | null;
  priority?: string;
  priority_score?: number;
  queue_position?: number | null;
  sla_remaining_hours?: number | null;
  sla_deadline?: string | null;
  category?: string | null;
  severity?: number | null;
  tier?: number;
  estimated_review_time?: string;
}

export interface AgentQueueResponse {
  total_queue_size: number;
  my_assigned: number;
  my_in_review: number;
  complaints: AgentQueueItem[];
}

export interface AgentWorkspaceActionBody {
  agent_id: string;
  action: "ACCEPT" | "EDIT" | "REJECT" | "MANUAL_ESCALATE";
  edited_response?: string | null;
  rejection_reason?: string | null;
  escalation_target_tier?: number | null;
  notes?: string;
}

export interface AgentMetricsResponse {
  agent_id: string;
  total_reviewed: number;
  avg_review_time: string;
  acceptance_rate?: number | null;
  edit_rate?: number | null;
  rejection_rate?: number | null;
  escalation_rate?: number | null;
  current_workload: number;
  categories_handled?: Record<string, number>;
}

export interface TeamMetricsResponse {
  tier_level: number;
  agent_count: number;
  total_reviewed: number;
  queue_size: number;
  agents: AgentMetricsResponse[];
}

/** Full review package from GET .../complaint/{id}/context */
export interface AgentComplaintContext {
  complaint_id?: string;
  complaint_summary?: {
    masked_text?: string;
    channel?: string;
    customer_id?: string;
    submitted_at?: string;
    current_tier?: number;
    status?: string;
    identity_status?: 'provisional' | 'verified' | 'unverifiable';
    cif_id?: string | null;
    linked_complaint_ids?: string[];
    pending_info_request?: boolean;
    duplicate_status?: 'possible_duplicate' | 'confirmed_duplicate' | 'merged';
    duplicate_of?: string[];
  };
  ai_analysis?: {
    classification?: { category?: string; confidence?: number };
    sentiment?: {
      emotion?: string;
      urgency_score?: number;
      escalation_flag?: boolean;
    };
    severity?: { level?: number; score?: number; breakdown?: unknown };
    rbi_compliance?: {
      compliance_category?: string;
      is_rbi_reportable?: boolean;
      tat_deadline?: string | null;
    };
  };
  draft_response?: {
    text?: string | null;
    confidence?: number;
    can_be_accepted?: boolean;
    root_cause?: string;
    action_steps?: string[];
    grounding_warnings?: unknown[];
    confidence_breakdown?: Record<string, number>;
  };
  escalation_analysis?: {
    should_escalate?: boolean;
    reasoning?: string;
    signals_detected?: unknown[];
  };
  suggested_actions?: string[];
  knowledge_references?: Array<{
    category?: string;
    similarity?: number;
    resolution_text?: string;
  }>;
  customer_history?: Record<string, unknown>;
  timeline?: Array<{ event: string; timestamp?: string | null }>;
  agent_decisions_trace?: Array<{
    agent?: string;
    decision?: string;
    confidence?: number;
  }>;
  note?: string;
}

export interface NextComplaintResponse {
  message: string;
  complaint: AgentComplaintContext | null;
  queue_info?: Record<string, unknown>;
}

// ── Typed endpoint helpers ────────────────────────────────────────────────────

export const api = {
  complaints: {
    submit: (form: FormData, idempotencyKey: string) =>
      apiPostForm<SubmitResponse>("/api/v1/complaints/submit", form, {
        "X-Idempotency-Key": idempotencyKey,
      }),
    list: (params?: {
      route?: string;
      category?: string;
      limit?: number;
      offset?: number;
    }) => {
      const qs = new URLSearchParams();
      if (params?.route) qs.set("route", params.route);
      if (params?.category) qs.set("category", params.category);
      qs.set("limit", String(params?.limit ?? 50));
      qs.set("offset", String(params?.offset ?? 0));
      return apiGet<ComplaintsListResponse>(`/api/v1/complaints/?${qs}`);
    },
    get: (id: string) => apiGet<ApiComplaint>(`/api/v1/complaints/${id}`),
    explanation: (id: string) =>
      apiGet<ExplanationResponse>(`/api/v1/complaints/${id}/explanation`),
    shadowOverride: (
      id: string,
      body: {
        agent_id: string;
        corrected_response: string;
        override_reason: string;
      },
    ) =>
      apiPost<ShadowOverrideResponse>(
        `/api/v1/complaints/${id}/shadow-override`,
        body,
      ),
    escalationStatus: (id: string) =>
      apiGet<EscalationStatusResponse>(
        `/api/v1/complaints/${id}/escalation-status`,
      ),
  },
  pipeline: {
    run: (complaintId: string) =>
      apiPost<PipelineRunResponse>(`/api/v1/pipeline/run/${complaintId}`),
  },
  dashboard: {
    stats: (days = 30) =>
      apiGet<DashboardStats>(`/api/v1/dashboard/stats?days=${days}`),
    csatTrends: (days = 30) =>
      apiGet<CSATTrends>(`/api/v1/dashboard/csat-trends?days=${days}`),
    pipelineHealth: (days = 7) =>
      apiGet<PipelineHealth>(`/api/v1/dashboard/pipeline-health?days=${days}`),
    rootCause: (params?: { min_rating?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.min_rating !== undefined)
        qs.set("min_rating", String(params.min_rating));
      if (params?.limit !== undefined) qs.set("limit", String(params.limit));
      return apiGet<RootCauseAnalysis>(`/api/v1/dashboard/root-cause?${qs}`);
    },
  },
  agent: {
    queue: (p: {
      agentId: string;
      tierLevel: number;
      statusFilter?: string;
    }) => {
      const qs = new URLSearchParams();
      qs.set("agent_id", p.agentId);
      qs.set("tier_level", String(p.tierLevel));
      if (p.statusFilter) qs.set("status_filter", p.statusFilter);
      return apiGet<AgentQueueResponse>(`/api/v1/agent/queue?${qs}`);
    },
    complaintContext: (complaintId: string, agentId: string) =>
      apiGet<AgentComplaintContext>(
        `/api/v1/agent/complaint/${encodeURIComponent(complaintId)}/context?agent_id=${encodeURIComponent(agentId)}`,
      ),
    submitAction: (complaintId: string, body: AgentWorkspaceActionBody) =>
      apiPost(
        `/api/v1/agent/complaint/${encodeURIComponent(complaintId)}/action`,
        body,
      ),
    nextComplaint: (body: { agent_id: string; tier_level: number }) =>
      apiPost<NextComplaintResponse>("/api/v1/agent/next-complaint", body),
    recoverStuck: (tierLevel: number) =>
      apiPost<{ recovered: number; total_stuck: number; message: string }>(
        `/api/v1/agent/recover-stuck-complaints?tier_level=${tierLevel}`,
      ),
    metrics: (agentId: string, dateFrom?: string, dateTo?: string) => {
      const qs = new URLSearchParams();
      if (dateFrom) qs.set("date_from", dateFrom);
      if (dateTo) qs.set("date_to", dateTo);
      const s = qs.toString();
      return apiGet<AgentMetricsResponse>(
        `/api/v1/agent/metrics/${encodeURIComponent(agentId)}${s ? `?${s}` : ""}`,
      );
    },
    teamMetrics: (tierLevel: number, dateFrom?: string, dateTo?: string) => {
      const qs = new URLSearchParams();
      if (dateFrom) qs.set("date_from", dateFrom);
      if (dateTo) qs.set("date_to", dateTo);
      const s = qs.toString();
      return apiGet<TeamMetricsResponse>(
        `/api/v1/agent/team-metrics/${tierLevel}${s ? `?${s}` : ""}`,
      );
    },
  },
  feedback: {
    submitAgent: (body: AgentFeedbackBody) =>
      apiPost("/api/v1/feedback/agent", body),
    datasetStats: () =>
      apiGet<DatasetStatsResponse>("/api/v1/feedback/dataset-stats"),
    datasetRecords: (limit = 50) =>
      apiGet<DatasetRecordsResponse>(
        `/api/v1/feedback/dataset-records?limit=${limit}`,
      ),
    triggerSurvey: (complaintId: string) =>
      apiPost<TriggerSurveyResponse>(
        `/api/v1/feedback/trigger-survey/${complaintId}`,
      ),
    submitCustomer: (body: CustomerFeedbackBody) =>
      apiPost<CustomerFeedbackResponse>("/api/v1/feedback/customer", body),
    exportDatasetPreview: (params?: ExportDatasetQuery) =>
      apiGet<DatasetExportPreviewResponse>(
        `/api/v1/feedback/export-dataset?${buildExportDatasetSearchParams({ ...params, preview: true })}`,
      ),
    /** Opens browser download for JSONL, or resolves to JSON if API returns no rows / empty export */
    exportDatasetDownload: (params?: Omit<ExportDatasetQuery, "preview">) =>
      downloadFineTuneDatasetFile(params),
  },
  rbi: {
    report: () => apiGet<RBIReport>("/api/v1/rbi/report"),
    pending: (hrs = 24) =>
      apiGet<RBIPending>(`/api/v1/rbi/pending?hours_threshold=${hrs}`),
    categories: () => apiGet<RBICategories>("/api/v1/rbi/categories"),
    log: (id: string) => apiPost(`/api/v1/rbi/log/${id}`),
  },
  sla: {
    summary: () => apiGet<SLASummary>("/api/v1/sla/summary"),
    atRisk: () => apiGet<SLAAtRisk>("/api/v1/sla/at-risk"),
  },
  kb: {
    reference: () => apiGet<KBReference>("/api/v1/admin/kb/reference"),
    metrics: () => apiGet<KBMetrics>("/api/v1/admin/kb/metrics"),
    entries: (params?: KBEntriesParams) => {
      const qs = new URLSearchParams();
      if (params?.category) qs.set("category", params.category);
      if (params?.tier_level !== undefined)
        qs.set("tier_level", String(params.tier_level));
      if (params?.verified !== undefined)
        qs.set("verified", String(params.verified));
      if (params?.search) qs.set("search", params.search);
      qs.set("page", String(params?.page ?? 1));
      qs.set("page_size", String(params?.page_size ?? 20));
      return apiGet<KBEntriesResponse>(`/api/v1/admin/kb/entries?${qs}`);
    },
    createEntry: (body: KBEntryPayload) =>
      apiPost<KBEntry>("/api/v1/admin/kb/entries", body),
    getEntry: (id: number) => apiGet<KBEntry>(`/api/v1/admin/kb/entries/${id}`),
    updateEntry: (id: number, body: KBEntryPayload) =>
      apiPut<KBEntry>(`/api/v1/admin/kb/entries/${id}`, body),
    deleteEntry: (id: number) => apiDelete(`/api/v1/admin/kb/entries/${id}`),
    analytics: () => apiGet<KBAnalytics>("/api/v1/admin/kb/analytics"),
    bulkValidate: (formData: FormData) =>
      apiPostForm<KBBulkValidateResult>(
        "/api/v1/admin/kb/bulk-validate",
        formData,
      ),
    bulkImport: (formData: FormData) =>
      apiPostForm<KBBulkImportResult>("/api/v1/admin/kb/bulk-import", formData),
    queue: () => apiGet<KBQueueEntry[]>("/api/v1/admin/kb/queue"),
    approveQueue: (id: number, body: KBEntryPayload) =>
      apiPost<KBEntry>(`/api/v1/admin/kb/queue/${id}/approve`, body),
    rejectQueue: (id: number, reason: string) =>
      apiPost(`/api/v1/admin/kb/queue/${id}/reject`, { reason }),
    bulkApprove: (body: {
      min_quality_score: number;
      tier_level?: number;
      category?: string;
    }) => apiPost("/api/v1/admin/kb/queue/bulk-approve", body),
    bulkReject: (reason: string) =>
      apiPost("/api/v1/admin/kb/queue/bulk-reject", { reason }),
    processQueue: () => apiPost<string>("/api/v1/admin/kb/jobs/process-queue"),
    weeklyReview: () => apiPost("/api/v1/admin/kb/jobs/weekly-review"),
    cleanup: () => apiPost("/api/v1/admin/kb/jobs/cleanup"),
  },
  settings: {
    getAutoMode: () =>
      apiGet<{ enabled: boolean }>("/api/v1/settings/auto-mode"),
    setAutoMode: (enabled: boolean) =>
      apiPost<{ enabled: boolean }>("/api/v1/settings/auto-mode", { enabled }),
  },
  duplicates: {
    merge: (primaryId: string, secondaryId: string) =>
      apiPost<{ status: string; primary_id: string; secondary_id: string }>(
        '/api/v1/duplicates/merge',
        { primary_id: primaryId, secondary_id: secondaryId },
      ),
    confirmSamePerson: (complaintId: string) =>
      apiPost<{ status: string; complaint_id: string }>(
        `/api/v1/duplicates/${encodeURIComponent(complaintId)}/confirm-same-person`,
      ),
  },
  incidents: {
    list: (params?: { min_priority?: string }) => {
      const qs = new URLSearchParams();
      if (params?.min_priority) qs.set("min_priority", params.min_priority);
      return apiGet<IncidentAlertsResponse>(`/api/v1/clusters/alerts?${qs}`);
    },
  },
};

// ── Incident alert types (Predictive Complaint Intelligence) ─────────────────

export interface IncidentAlert {
  cluster_id: string;
  event_type: string;
  product?: string | null;
  region?: string | null;
  alert_priority: "low" | "medium" | "high" | "critical";
  risk_score?: number | null;
  growth_probability?: number | null;
  predicted_impact_customers?: number | null;
  confidence_score?: number | null;
  distinct_customers_24h?: number | null;
  rbi_reportable_ratio?: number | null;
  last_seen_at?: string | null;
  snapshot_time?: string | null;
  departments: string[];
}

export interface IncidentAlertsResponse {
  alerts: IncidentAlert[];
  total: number;
}

// ── Backend API response types ────────────────────────────────────────────────

export interface SubmitResponse {
  complaint_id: string;
  complaint_text: string;
  channel: string;
  has_image: boolean;
  image_url?: string | null;
  extraction_method?: string | null;
  extracted_image_text?: string | null;
  merged_text: string;
  status: string;
  message: string;
}

export interface PipelineRunResponse {
  message: string;
  complaint_id: string;
  stream_url?: string;
  current_status?: string;
  final_route?: string;
  category?: string;
  severity?: number;
  route?: string;
}

/** Single grounding warning from LLM judge (see grounding_agent.py) */
export interface GroundingWarningItem {
  type?: string;
  claim?: string;
  issue?: string;
  suggestion?: string;
}

export interface ApiComplaint {
  complaint_id: string;
  customer_id: string;
  channel: string;
  original_text?: string;
  merged_text?: string;
  masked_text?: string;
  language?: string;
  category?: string;
  category_confidence?: number;
  sentiment?: string;
  urgency_score?: number;
  escalation_flag?: boolean;
  compliance_category?: string;
  is_rbi_reportable?: boolean;
  rbi_supervisor_override?: boolean;
  severity?: number;
  severity_score?: number;
  draft_response?: string;
  root_cause?: string;
  action_steps?: string[];
  confidence_score?: number;
  grounding_score?: number;
  /** From Grounding agent: structured objects; legacy may be plain strings */
  grounding_warnings?: (string | GroundingWarningItem)[];
  route?: string;
  risk_score?: number;
  sla_hours?: number;
  rbi_tat_deadline?: string;
  pipeline_status?: string;
  status?: string;
  /** Shadow auto-send: replacement deadline for human correction */
  shadow_override_deadline?: string | null;
  shadow_overridden?: boolean;
  auto_sent_at?: string | null;
  assigned_tier?: number | null;
  response_tier?: string | null;
  current_tier?: number | null;
  image_url?: string;
  extraction_method?: string;
  is_duplicate?: boolean;
  duplicate_of?: string[];
  duplicate_similarity?: number;
  duplicate_status?: 'possible_duplicate' | 'confirmed_duplicate' | 'merged';
  merged_into?: string | null;
  created_at?: string;
  /** Identity resolution fields */
  identity_status?: 'provisional' | 'verified' | 'unverifiable';
  cif_id?: string | null;
  linked_complaint_ids?: string[];
  pending_info_request?: boolean;
}

export interface ComplaintsListResponse {
  total: number;
  limit: number;
  offset: number;
  complaints: ApiComplaint[];
}

export interface AgentDecision {
  agent_name: string;
  agent_order: number;
  status: string;
  decision?: string;
  confidence?: number;
  reasoning?: string;
  evidence?: string[];
  duration_ms?: number;
  metadata?: Record<string, unknown>;
  error_message?: string;
}

export interface ExplanationResponse {
  complaint_id: string;
  pipeline_status: string;
  final_route?: string;
  category?: string;
  severity?: number;
  total_agents: number;
  explanation_trace: AgentDecision[];
}

/** GET .../escalation-status — read-only snapshot of tier routing & audit trail */
export interface EscalationStatusResponse {
  complaint_id: string;
  is_escalating: boolean;
  current_tier: number | null;
  escalation_count: number;
  escalation_path: number[];
  max_tier_reached: number;
  last_escalation_at: string | null;
  escalation_loop_detected: boolean;
  next_action: string;
  escalation_history: Array<{
    from_tier?: number | null;
    to_tier?: number | null;
    escalation_reason?: string | null;
    confidence_before?: number | null;
    escalation_decision_reasoning?: string | null;
    signals_detected?: unknown;
    escalated_at?: string | null;
    status?: string | null;
  }>;
}

export interface ShadowOverrideResponse {
  complaint_id: string;
  override_applied: boolean;
  corrected_response_sent: boolean;
  agent_id: string;
  override_reason: string;
  message: string;
}

export interface DashboardStats {
  period_days: number;
  generated_at: string;
  overview: {
    total_complaints: number;
    auto_responded: number;
    human_review: number;
    pending_pipeline: number;
    auto_respond_rate_percent: number;
    rbi_reportable: number;
    rbi_reportable_rate_percent: number;
    closed: number;
    open: number;
    duplicate_count: number;
    auto_sent_count: number;
  };
  averages: {
    avg_severity: number;
    avg_confidence_score: number;
    avg_risk_score: number;
  };
  distributions: {
    by_category: Array<{ category: string; count: number; percent: number }>;
    by_sentiment: Array<{ sentiment: string; count: number; percent: number }>;
    by_severity: Array<{
      severity: number;
      label: string;
      count: number;
      percent: number;
    }>;
    by_channel: Array<{ channel: string; count: number; percent: number }>;
    by_tier: Array<{
      tier: number;
      label: string;
      count: number;
      percent: number;
    }>;
  };
  daily_volume: Array<{ date: string; count: number }>;
}

export interface CSATTrends {
  period_days: number;
  overall?: {
    total_responses: number;
    average_csat: number;
    csat_label: string;
  };
  satisfaction_distribution?: {
    very_dissatisfied: number;
    dissatisfied: number;
    neutral: number;
    satisfied: number;
    very_satisfied: number;
  };
  by_category?: Array<{
    category: string;
    avg_csat: number;
    response_count: number;
  }>;
  by_channel?: Array<{
    channel: string;
    avg_csat: number;
    response_count: number;
  }>;
  weekly_trend?: Array<{
    week: string;
    avg_csat: number | null;
    response_count: number;
  }>;
  message?: string;
}

export interface PipelineHealth {
  period_days: number;
  summary?: {
    total_agent_executions: number;
    overall_success_rate: number;
    total_failures: number;
  };
  per_agent?: Array<{
    agent_name: string;
    agent_order: number;
    total_runs: number;
    success_rate: number;
    failure_count: number;
    avg_duration_ms: number;
  }>;
  message?: string;
}

export interface AgentFeedbackBody {
  complaint_id: string;
  agent_id: string;
  action: "accept" | "edit" | "reject" | "escalate";
  original_draft: string;
  final_response?: string;
  rejection_reason?: string;
}

export interface DatasetStatsResponse {
  total_records: number;
  message?: string;
  unexported_records?: number;
  exported_records?: number;
  quality_breakdown?: {
    "accepted_agent_1.0": number;
    "edited_agent_0.5": number;
    "rejected_agent_0.0": number;
  };
  avg_combined_score?: number;
  by_category?: Record<string, number>;
  fine_tuning_readiness?: {
    current: number;
    recommended_minimum: number;
    percentage: number;
    status: string;
  };
  next_steps?: string;
}

/** @deprecated alias — use DatasetStatsResponse */
export type DatasetStats = DatasetStatsResponse;

export interface TriggerSurveyResponse {
  complaint_id: string;
  survey_triggered: boolean;
  status_updated_to?: string;
  message: string;
  survey_fields?: Record<string, string>;
}

export interface CustomerFeedbackBody {
  complaint_id: string;
  customer_id: string;
  rating: number;
  issue_tags?: string[];
  feedback_text?: string;
}

export interface CustomerFeedbackResponse {
  status: string;
  message: string;
  rating?: number;
  combined_rl_score?: number;
  kb_promoted?: boolean;
  calibration_triggered?: boolean;
}

export interface DatasetExportPreviewResponse {
  preview_mode?: boolean;
  total_records_to_export?: number;
  avg_combined_score?: number;
  by_category?: Record<string, number>;
  by_agent_rating?: Record<string, number>;
  fine_tuning_readiness?: string;
  hint?: string;
  message?: string;
  total_records?: number;
}

export interface DatasetRecordsResponse {
  limit: number;
  count: number;
  records: DatasetRecordRow[];
  source_note: string;
}

export interface DatasetRecordRow {
  id: number | string;
  complaint_id: string;
  category?: string | null;
  agent_rating?: number | null;
  customer_rating?: number | null;
  combined_score?: number | null;
  exported?: boolean | null;
  created_at?: string | null;
  complaint_preview: string;
}

export interface RBIReport {
  report_metadata: { generated_at: string; report_type: string };
  summary: {
    total_complaints: number;
    rbi_reportable_complaints: number;
    tat_compliance_rate_percent: number;
    tat_breached_count: number;
    human_review_count: number;
    auto_respond_count: number;
    auto_respond_rate_percent: number;
  };
  rbi_category_breakdown: Array<{
    rbi_category: string;
    display_label: string;
    total_count: number;
    human_review_count: number;
    resolved_count: number;
    tat_breached_count: number;
  }>;
  compliance_status: string;
  compliance_notes: string[];
}

export interface RBIPending {
  generated_at: string;
  summary: {
    total_pending_rbi: number;
    breached_count: number;
    warning_count: number;
    safe_count: number;
  };
  breached: Array<{
    complaint_id: string;
    compliance_category: string;
    hours_remaining: number;
    deadline_readable: string;
    category: string;
    alert_level: string;
  }>;
  approaching_breach: Array<{
    complaint_id: string;
    compliance_category: string;
    hours_remaining: number;
    deadline_readable: string;
    category: string;
    alert_level: string;
  }>;
}

export interface RBICategories {
  total_categories: number;
  categories: Array<{
    category_code: string;
    display_label: string;
    is_rbi_reportable: boolean;
    supervisor_override_always_human: boolean;
    sla_label: string;
    resolution_hours: number;
    penalty_per_day: number;
    penalty_description: string;
  }>;
}

export interface SLASummary {
  generated_at: string;
  overall_health: string;
  open_complaints: number;
  human_review_queue: number;
  rbi_tat_breached: number;
  rbi_tat_at_risk_24h: number;
  predicted_breach: { critical: number; high: number; total_at_risk: number };
  action_required: boolean;
}

// ── KB Admin types ────────────────────────────────────────────────────────────

export interface KBReference {
  categories: string[];
  tier_labels: Record<string, string>;
  tier_scope_formats: Record<string, string | null>;
  regions: string[];
  embedding_model: string;
  embedding_dimensions: number;
}

export interface KBMetrics {
  total: number;
  verified: number;
  pending: number;
  avg_quality: number;
  tier_distribution: Array<{
    tier_level: number;
    label: string;
    count: number;
  }>;
  coverage_gaps: Array<{ category: string; count: number; needed: number }>;
  recent_additions: KBEntry[];
}

export interface KBEntry {
  id: number;
  tier_level: number;
  tier_scope: string;
  category: string;
  issue_type: string;
  quality_score: number;
  verified: boolean;
  usage_count: number;
  source: string;
  created_at: string;
  updated_at: string;
  resolution_text: string;
}

export interface KBEntryPayload {
  tier_level: number;
  tier_scope: string;
  category: string;
  issue_type: string;
  resolution_text: string;
  quality_score: number;
  verified: boolean;
}

export interface KBEntriesParams {
  category?: string;
  tier_level?: number;
  verified?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface KBEntriesResponse {
  entries: KBEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface KBQueueEntry {
  id: number;
  complaint_id: string;
  resolution_text: string;
  scheduled_for: string;
  added_to_kb: boolean;
  created_at: string;
  tier_level: number;
  tier_scope: string;
  category: string;
  issue_type: string;
  confidence_score: number;
  recommended_quality_score: number;
  quality_signals_json: Record<string, unknown>;
  agent_action: string;
  customer_feedback_score: number;
  resolution_type: string;
  rejection_reason: string;
}

export interface KBAnalytics {
  top_entries_by_usage: Array<Record<string, unknown>>;
  category_usage: Array<Record<string, unknown>>;
  tier_coverage_matrix: Array<Record<string, unknown>>;
  category_gaps: Array<Record<string, unknown>>;
  quality_distribution: Array<Record<string, unknown>>;
  tier_quality: Array<Record<string, unknown>>;
}

export interface KBBulkValidateResult {
  total: number;
  valid: number;
  errors: number;
  rows: Array<Record<string, unknown>>;
}

export interface KBBulkImportResult {
  total_rows: number;
  successful: number;
  failed: number;
  errors: Array<Record<string, unknown>>;
}

export interface RootCauseAnalysis {
  message?: string;
  total_analysed: number;
  common_themes?: Array<{
    theme: string;
    frequency: number;
    example_complaints: string[];
  }>;
  category_breakdown?: Record<string, number>;
  sentiment_patterns?: Record<string, number>;
  recommendations?: string[];
}

export interface SLAAtRisk {
  generated_at: string;
  total_open_complaints: number;
  at_risk_count: number;
  risk_summary: Record<string, number>;
  system_alert?: string | null;
  predictions: Array<{
    complaint_id: string;
    breach_probability: number;
    risk_level: string;
    estimated_breach_in_hours?: number;
    category?: string;
    severity?: number;
    is_rbi_reportable?: boolean;
  }>;
}

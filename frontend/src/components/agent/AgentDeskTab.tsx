import { useCallback, useEffect, useRef, useState } from "react";
import {
  UserCircle2,
  RefreshCw,
  Loader2,
  Inbox,
  Users,
  ChevronRight,
  X,
  CheckCircle,
  Edit3,
  XCircle,
  ArrowUpCircle,
  AlertTriangle,
  Clock,
} from "lucide-react";
import {
  api,
  type AgentComplaintContext,
  type AgentQueueItem,
} from "../../lib/api";
import { useApiData } from "../../hooks/useApiData";

const STORAGE_AGENT = "ub_agent_desk_id";
const STORAGE_TIER = "ub_agent_desk_tier";

function loadStoredAgent(): string {
  try {
    return localStorage.getItem(STORAGE_AGENT) ?? "desk_agent";
  } catch {
    return "desk_agent";
  }
}

function loadStoredTier(): number {
  try {
    const t = parseInt(localStorage.getItem(STORAGE_TIER) ?? "1", 10);
    return Number.isFinite(t) && t >= 1 && t <= 5 ? t : 1;
  } catch {
    return 1;
  }
}

function urgencyWords(priority?: string): string {
  switch (priority) {
    case "CRITICAL": return "Very urgent";
    case "HIGH":     return "Urgent";
    case "MEDIUM":   return "Normal";
    case "LOW":      return "Can wait";
    default:         return priority ?? "—";
  }
}

function queueStatusWords(status?: string): string {
  switch (status) {
    case "QUEUED":    return "Waiting";
    case "ASSIGNED":  return "Assigned";
    case "IN_REVIEW": return "In review";
    default:          return status ?? "—";
  }
}

function percentOrDash(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${Math.round(v * 100)}%`;
}

// ── Case Detail Modal ─────────────────────────────────────────────────────────
type ActionMode = "idle" | "edit" | "reject" | "escalate";

function CaseDetailModal({
  caseId,
  staffId,
  supportLevel,
  onClose,
  onActionComplete,
}: {
  caseId: string;
  staffId: string;
  supportLevel: number;
  onClose: () => void;
  onActionComplete: () => void;
}) {
  const [details, setDetails] = useState<AgentComplaintContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mode, setMode] = useState<ActionMode>("idle");
  const [editedText, setEditedText] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [escalateTier, setEscalateTier] = useState(Math.min(supportLevel + 1, 5));
  const [escalateReason, setEscalateReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionResult, setActionResult] = useState<{ ok: boolean; msg: string } | null>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const ctx = await api.agent.complaintContext(caseId, staffId);
        if (cancelled) return;
        setDetails(ctx);
        const draft = ctx.draft_response as { text?: string | null } | undefined;
        setEditedText(draft?.text ?? "");
      } catch (e) {
        if (!cancelled)
          setLoadError(e instanceof Error ? e.message : "Could not load case");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [caseId, staffId]);

  const submitAction = async (
    action: "ACCEPT" | "EDIT" | "REJECT" | "MANUAL_ESCALATE",
  ) => {
    setSubmitting(true);
    try {
      await api.agent.submitAction(caseId, {
        agent_id: staffId,
        action,
        edited_response:
          action === "EDIT" ? editedText : undefined,
        rejection_reason:
          action === "REJECT"
            ? rejectReason
            : action === "MANUAL_ESCALATE"
              ? escalateReason
              : undefined,
        escalation_target_tier:
          action === "MANUAL_ESCALATE" ? escalateTier : undefined,
      });
      setActionResult({ ok: true, msg: "Action submitted successfully. Closing…" });
      setTimeout(() => {
        onActionComplete();
        onClose();
      }, 1200);
    } catch (e) {
      setActionResult({
        ok: false,
        msg: e instanceof Error ? e.message : "Action failed",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const summary = details?.complaint_summary as
    | {
        masked_text?: string;
        channel?: string;
        customer_id?: string;
        submitted_at?: string;
        current_tier?: number;
        status?: string;
      }
    | undefined;

  const ai = details?.ai_analysis;
  const draft = details?.draft_response;
  const refs = details?.knowledge_references;

  const severityColor =
    (ai?.severity?.level ?? 0) >= 4
      ? "bg-red-50 text-red-700"
      : (ai?.severity?.level ?? 0) >= 3
        ? "bg-amber-50 text-amber-700"
        : "bg-gray-100 text-gray-600";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Blurred backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal card */}
      <div className="relative z-10 w-full max-w-2xl bg-white rounded-2xl shadow-2xl flex flex-col max-h-[90vh] border border-gray-100">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0">
          <div>
            <p className="text-xs text-gray-400 mb-0.5">Case reference</p>
            <h2 className="text-sm font-bold text-gray-900 font-mono">
              {caseId}
            </h2>
            {ai?.classification?.category && (
              <p className="text-xs text-gray-500 mt-0.5">
                {ai.classification.category}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">
          {loading && (
            <div className="flex items-center justify-center gap-2 text-xs text-gray-400 py-12">
              <Loader2 size={16} className="animate-spin" /> Loading case…
            </div>
          )}
          {loadError && (
            <p className="text-xs text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {loadError}
            </p>
          )}

          {!loading && details && (
            <>
              {/* Status chips */}
              {ai && (
                <div className="flex flex-wrap gap-1.5">
                  {ai.severity?.level != null && (
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${severityColor}`}
                    >
                      Severity {ai.severity.level}
                    </span>
                  )}
                  {ai.sentiment?.emotion && (
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700">
                      {ai.sentiment.emotion}
                    </span>
                  )}
                  {ai.sentiment?.urgency_score != null && (
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-orange-50 text-orange-700">
                      Urgency {ai.sentiment.urgency_score}
                    </span>
                  )}
                  {draft?.confidence != null && (
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        draft.confidence >= 0.8
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      AI confidence {Math.round(draft.confidence * 100)}%
                    </span>
                  )}
                  {ai.rbi_compliance?.is_rbi_reportable && (
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 flex items-center gap-1">
                      <AlertTriangle size={10} /> RBI Reportable
                    </span>
                  )}
                  {ai.sentiment?.escalation_flag && (
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700">
                      Escalation flagged
                    </span>
                  )}
                </div>
              )}

              {/* Complaint text */}
              <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
                <p className="text-xs font-semibold text-gray-500 mb-2">
                  What the customer said
                </p>
                <p className="text-xs text-gray-800 leading-relaxed whitespace-pre-wrap">
                  {summary?.masked_text ?? "—"}
                </p>
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-400">
                  {summary?.channel && (
                    <span>Channel: {summary.channel}</span>
                  )}
                  {summary?.customer_id && (
                    <span>Customer: {summary.customer_id}</span>
                  )}
                  {summary?.submitted_at && (
                    <span className="flex items-center gap-1">
                      <Clock size={10} />
                      {new Date(summary.submitted_at).toLocaleDateString(
                        "en-IN",
                        { day: "2-digit", month: "short", year: "numeric" },
                      )}
                    </span>
                  )}
                </div>
              </div>

              {/* Draft response / editable area */}
              <div className="rounded-xl border border-gray-100 p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold text-gray-500">
                    AI draft response
                  </p>
                  {draft?.can_be_accepted !== false && mode === "idle" && (
                    <span className="text-xs bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full">
                      Ready to send
                    </span>
                  )}
                </div>
                {mode === "edit" ? (
                  <textarea
                    value={editedText}
                    onChange={(e) => setEditedText(e.target.value)}
                    rows={6}
                    className="w-full text-xs border border-sky-200 rounded-lg px-3 py-2.5 text-gray-800 leading-relaxed focus:outline-none focus:ring-2 focus:ring-sky-300 resize-y"
                  />
                ) : (
                  <p className="text-xs text-gray-800 leading-relaxed whitespace-pre-wrap">
                    {draft?.text ?? "—"}
                  </p>
                )}
                {draft?.root_cause && (
                  <p className="text-xs text-gray-400">
                    Root cause: {draft.root_cause}
                  </p>
                )}
              </div>

              {/* Reject reason */}
              {mode === "reject" && (
                <div className="rounded-xl border border-red-100 bg-red-50 p-4 space-y-2">
                  <p className="text-xs font-semibold text-red-700">
                    Rejection reason (required)
                  </p>
                  <textarea
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    rows={3}
                    placeholder="Why is the AI draft not suitable for this case?"
                    className="w-full text-xs border border-red-200 rounded-lg px-3 py-2.5 text-gray-800 leading-relaxed bg-white focus:outline-none focus:ring-2 focus:ring-red-300 resize-y"
                  />
                </div>
              )}

              {/* Escalate fields */}
              {mode === "escalate" && (
                <div className="rounded-xl border border-violet-100 bg-violet-50 p-4 space-y-3">
                  <p className="text-xs font-semibold text-violet-700">
                    Manual escalation
                  </p>
                  <div className="flex items-center gap-3">
                    <label className="text-xs text-gray-600">
                      Escalate to tier
                    </label>
                    <input
                      type="number"
                      min={supportLevel + 1}
                      max={5}
                      value={escalateTier}
                      onChange={(e) =>
                        setEscalateTier(
                          Number(e.target.value) || supportLevel + 1,
                        )
                      }
                      className="w-20 text-sm border border-violet-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-violet-300"
                    />
                  </div>
                  <textarea
                    value={escalateReason}
                    onChange={(e) => setEscalateReason(e.target.value)}
                    rows={3}
                    placeholder="Why does this need to go to a higher tier?"
                    className="w-full text-xs border border-violet-200 rounded-lg px-3 py-2.5 text-gray-800 leading-relaxed bg-white focus:outline-none focus:ring-2 focus:ring-violet-300 resize-y"
                  />
                </div>
              )}

              {/* Knowledge references */}
              {refs && refs.length > 0 && (
                <div className="rounded-xl border border-gray-100 p-4 space-y-2">
                  <p className="text-xs font-semibold text-gray-500">
                    Similar past cases
                  </p>
                  {refs.map((ref, i) => (
                    <div key={i} className="rounded-lg bg-gray-50 p-3 text-xs">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-gray-700">
                          {ref.category ?? "—"}
                        </span>
                        {ref.similarity != null && (
                          <span className="text-gray-400">
                            {Math.round(ref.similarity * 100)}% match
                          </span>
                        )}
                      </div>
                      <p className="text-gray-600 line-clamp-2">
                        {ref.resolution_text}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* Action result banner */}
              {actionResult && (
                <p
                  className={`text-xs rounded-lg px-3 py-2 border ${
                    actionResult.ok
                      ? "bg-emerald-50 text-emerald-700 border-emerald-100"
                      : "bg-red-50 text-red-700 border-red-100"
                  }`}
                >
                  {actionResult.msg}
                </p>
              )}
            </>
          )}
        </div>

        {/* Sticky action bar */}
        {!loading && details && !actionResult && (
          <div className="border-t border-gray-100 px-6 py-4 flex-shrink-0 rounded-b-2xl bg-gray-50">
            {mode === "idle" && (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void submitAction("ACCEPT")}
                  disabled={submitting}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                >
                  {submitting ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <CheckCircle size={13} />
                  )}
                  Accept & send
                </button>
                <button
                  type="button"
                  onClick={() => setMode("edit")}
                  disabled={submitting}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-sky-700 text-white text-xs font-semibold hover:bg-sky-800 disabled:opacity-50 transition-colors"
                >
                  <Edit3 size={13} /> Edit draft
                </button>
                <button
                  type="button"
                  onClick={() => setMode("reject")}
                  disabled={submitting}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-600 text-white text-xs font-semibold hover:bg-red-700 disabled:opacity-50 transition-colors"
                >
                  <XCircle size={13} /> Reject
                </button>
                {supportLevel < 5 && (
                  <button
                    type="button"
                    onClick={() => setMode("escalate")}
                    disabled={submitting}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-700 text-white text-xs font-semibold hover:bg-violet-800 disabled:opacity-50 transition-colors"
                  >
                    <ArrowUpCircle size={13} /> Escalate
                  </button>
                )}
              </div>
            )}

            {mode === "edit" && (
              <div className="flex gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => void submitAction("EDIT")}
                  disabled={submitting || !editedText.trim()}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-sky-700 text-white text-xs font-semibold hover:bg-sky-800 disabled:opacity-50 transition-colors"
                >
                  {submitting ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <CheckCircle size={13} />
                  )}
                  Send edited response
                </button>
                <button
                  type="button"
                  onClick={() => setMode("idle")}
                  disabled={submitting}
                  className="px-4 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-100 transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}

            {mode === "reject" && (
              <div className="flex gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => void submitAction("REJECT")}
                  disabled={submitting || !rejectReason.trim()}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-600 text-white text-xs font-semibold hover:bg-red-700 disabled:opacity-50 transition-colors"
                >
                  {submitting ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <XCircle size={13} />
                  )}
                  Confirm rejection
                </button>
                <button
                  type="button"
                  onClick={() => setMode("idle")}
                  disabled={submitting}
                  className="px-4 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-100 transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}

            {mode === "escalate" && (
              <div className="flex gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => void submitAction("MANUAL_ESCALATE")}
                  disabled={submitting}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-700 text-white text-xs font-semibold hover:bg-violet-800 disabled:opacity-50 transition-colors"
                >
                  {submitting ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <ArrowUpCircle size={13} />
                  )}
                  Confirm escalation
                </button>
                <button
                  type="button"
                  onClick={() => setMode("idle")}
                  disabled={submitting}
                  className="px-4 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-100 transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Complaint row used in both tables ─────────────────────────────────────────
function QueueRow({
  row,
  isMyCase,
  onOpen,
}: {
  row: AgentQueueItem;
  isMyCase: boolean;
  onOpen: () => void;
}) {
  return (
    <tr className="border-t border-gray-50 hover:bg-gray-50/80">
      <td className="py-2 px-3 font-mono font-semibold text-sky-700">
        {row.id}
        {isMyCase && (
          <span className="ml-2 text-xs bg-sky-100 text-sky-700 px-1.5 py-0.5 rounded-full font-sans font-medium">
            mine
          </span>
        )}
      </td>
      <td className="py-2 px-3">{row.category ?? "—"}</td>
      <td className="py-2 px-3">{urgencyWords(row.priority)}</td>
      <td className="py-2 px-3">{queueStatusWords(row.queue_status)}</td>
      <td className="py-2 px-3 text-right">{row.estimated_review_time ?? "—"}</td>
      <td className="py-2 px-3 text-right">
        {row.sla_remaining_hours != null
          ? row.sla_remaining_hours < 0
            ? `${Math.abs(row.sla_remaining_hours)}h overdue`
            : `${row.sla_remaining_hours}h`
          : "—"}
      </td>
      <td className="py-2 px-3">
        <button
          type="button"
          onClick={onOpen}
          className="text-sky-700 font-semibold hover:underline inline-flex items-center gap-0.5 text-xs"
        >
          Open <ChevronRight size={12} />
        </button>
      </td>
    </tr>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function AgentDeskTab() {
  const [draftName, setDraftName] = useState(loadStoredAgent);
  const [draftLevel, setDraftLevel] = useState(loadStoredTier);
  const [staffId, setStaffId] = useState(loadStoredAgent);
  const [supportLevel, setSupportLevel] = useState(loadStoredTier);
  const [modalCaseId, setModalCaseId] = useState<string | null>(null);

  const applyIdentity = useCallback(() => {
    const name = draftName.trim() || "desk_agent";
    const lvl = Math.min(5, Math.max(1, Math.floor(draftLevel)));
    try {
      localStorage.setItem(STORAGE_AGENT, name);
      localStorage.setItem(STORAGE_TIER, String(lvl));
    } catch {
      /* ignore */
    }
    setStaffId(name);
    setSupportLevel(lvl);
  }, [draftName, draftLevel]);

  const {
    data: myNumbers,
    loading: metricsLoading,
    error: metricsError,
    refetch: refetchMetrics,
  } = useApiData(() => api.agent.metrics(staffId), [staffId]);

  const {
    data: teamSnapshot,
    loading: teamLoading,
    error: teamError,
    refetch: refetchTeam,
  } = useApiData(() => api.agent.teamMetrics(supportLevel), [supportLevel]);

  const {
    data: waitingList,
    loading: queueLoading,
    error: queueError,
    refetch: refetchQueue,
  } = useApiData(
    () => api.agent.queue({ agentId: staffId, tierLevel: supportLevel }),
    [staffId, supportLevel],
  );

  // Self-heal: once per session, recover stuck complaints if queue is empty
  const recoveredRef = useRef(false);
  useEffect(() => {
    if (recoveredRef.current) return;
    if (queueLoading) return;
    if (!waitingList) return;
    if (waitingList.total_queue_size > 0) return;

    recoveredRef.current = true;
    api.agent
      .recoverStuck(supportLevel)
      .then((res) => {
        if (res.recovered > 0) refetchQueue();
      })
      .catch(() => {
        /* silent */
      });
  }, [queueLoading, waitingList, supportLevel, refetchQueue]);

  const refreshAll = () => {
    refetchMetrics();
    refetchTeam();
    refetchQueue();
  };

  const myCases =
    waitingList?.complaints.filter((c) => c.assigned_to === staffId) ?? [];
  const otherCases =
    waitingList?.complaints.filter((c) => c.assigned_to !== staffId) ?? [];

  const tableHeader = (
    <thead>
      <tr className="text-gray-500 bg-gray-50 text-left text-xs">
        <th className="py-2 px-3">Case reference</th>
        <th className="py-2 px-3">Topic</th>
        <th className="py-2 px-3">How urgent</th>
        <th className="py-2 px-3">Status</th>
        <th className="py-2 px-3 text-right">Est. time</th>
        <th className="py-2 px-3 text-right">SLA left</th>
        <th className="py-2 px-3 w-12" />
      </tr>
    </thead>
  );

  return (
    <div className="space-y-4">
      {/* Intro */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
        <div className="flex items-start gap-3 flex-wrap">
          <div className="w-10 h-10 rounded-xl bg-sky-50 flex items-center justify-center flex-shrink-0">
            <UserCircle2 size={22} className="text-sky-700" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-base font-bold text-gray-800">Agent desk</h1>
            <p className="text-xs text-gray-600 leading-relaxed mt-1">
              Your workspace: see your performance, cases assigned to you, and
              open any case to review and take action.
            </p>
          </div>
          <button
            type="button"
            onClick={refreshAll}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50"
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* Who you are */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm space-y-3">
        <h2 className="text-sm font-bold text-gray-800">
          Who is using this screen?
        </h2>
        <p className="text-xs text-gray-500">
          Enter the same staff login your bank uses for this tool, and pick your
          support level (1 = front line, higher numbers = more senior). We save
          this on this device so you do not have to type it every time.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 items-end">
          <label className="text-xs flex-1 w-full">
            <span className="text-gray-500 block mb-1">Staff ID</span>
            <input
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. desk_agent"
            />
          </label>
          <label className="text-xs w-full sm:w-36">
            <span className="text-gray-500 block mb-1">
              Support level (1–5)
            </span>
            <input
              type="number"
              min={1}
              max={5}
              value={draftLevel}
              onChange={(e) =>
                setDraftLevel(parseInt(e.target.value, 10) || 1)
              }
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <button
            type="button"
            onClick={applyIdentity}
            className="w-full sm:w-auto px-4 py-2 rounded-lg bg-sky-700 text-white text-xs font-semibold hover:bg-sky-800"
          >
            Save
          </button>
        </div>
      </div>

      {/* Your numbers */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        <h2 className="text-sm font-bold text-gray-800 mb-1">Your numbers</h2>
        <p className="text-xs text-gray-500 mb-4">
          Based on cases you have already finished (when the system has data).
        </p>
        {metricsLoading && (
          <div className="flex items-center gap-2 text-xs text-gray-400 py-6">
            <Loader2 size={14} className="animate-spin" /> Loading…
          </div>
        )}
        {metricsError && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            Could not load your numbers. Is the server running? ({metricsError})
          </p>
        )}
        {myNumbers && !metricsLoading && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">Cases you closed</div>
              <div className="text-2xl font-bold text-gray-900">
                {myNumbers.total_reviewed}
              </div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">Typical time per case</div>
              <div className="text-xl font-bold text-gray-900">
                {myNumbers.avg_review_time}
              </div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">
                Open cases assigned to you
              </div>
              <div className="text-2xl font-bold text-sky-700">
                {myNumbers.current_workload}
              </div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">
                You approved the draft as-is
              </div>
              <div className="text-xl font-bold text-emerald-700">
                {percentOrDash(myNumbers.acceptance_rate)}
              </div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">
                You changed the draft before sending
              </div>
              <div className="text-xl font-bold text-amber-800">
                {percentOrDash(myNumbers.edit_rate)}
              </div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">You turned down the draft</div>
              <div className="text-xl font-bold text-red-700">
                {percentOrDash(myNumbers.rejection_rate)}
              </div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">
                You sent the case to a higher level
              </div>
              <div className="text-xl font-bold text-violet-800">
                {percentOrDash(myNumbers.escalation_rate)}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Team */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Users size={16} className="text-gray-500" />
          <h2 className="text-sm font-bold text-gray-800">
            Your team at this support level
          </h2>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          Everyone working at support level <strong>{supportLevel}</strong>, and
          how many cases are still waiting in the shared line.
        </p>
        {teamLoading && (
          <div className="flex items-center gap-2 text-xs text-gray-400 py-4">
            <Loader2 size={14} className="animate-spin" /> Loading…
          </div>
        )}
        {teamError && (
          <p className="text-xs text-amber-800 bg-amber-50 border rounded-lg px-3 py-2">
            {teamError}
          </p>
        )}
        {teamSnapshot && !teamLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="rounded-lg bg-slate-50 border border-slate-100 p-3">
                <div className="text-gray-500">People on this level</div>
                <div className="text-lg font-bold text-gray-900">
                  {teamSnapshot.agent_count}
                </div>
              </div>
              <div className="rounded-lg bg-slate-50 border border-slate-100 p-3">
                <div className="text-gray-500">Cases closed by the team</div>
                <div className="text-lg font-bold text-gray-900">
                  {teamSnapshot.total_reviewed}
                </div>
              </div>
              <div className="rounded-lg bg-slate-50 border border-slate-100 p-3 sm:col-span-2">
                <div className="text-gray-500">
                  Cases waiting in the shared line
                </div>
                <div className="text-lg font-bold text-sky-700">
                  {teamSnapshot.queue_size}
                </div>
              </div>
            </div>
            {teamSnapshot.agents.length > 0 && (
              <div className="border border-gray-100 rounded-xl overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500 text-left">
                      <th className="py-2 px-3">Staff ID</th>
                      <th className="py-2 px-3 text-right">Cases closed</th>
                      <th className="py-2 px-3 text-right">Open now</th>
                    </tr>
                  </thead>
                  <tbody>
                    {teamSnapshot.agents.map((a) => (
                      <tr key={a.agent_id} className="border-t border-gray-50">
                        <td className="py-2 px-3 font-mono">{a.agent_id}</td>
                        <td className="py-2 px-3 text-right">
                          {a.total_reviewed}
                        </td>
                        <td className="py-2 px-3 text-right">
                          {a.current_workload}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* My assigned cases */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm space-y-4">
        <div className="flex items-center gap-2">
          <Inbox size={16} className="text-sky-600" />
          <div>
            <h2 className="text-sm font-bold text-gray-800">
              My assigned cases
            </h2>
            <p className="text-xs text-gray-500">
              Cases currently linked to your staff ID at support level{" "}
              <strong>{supportLevel}</strong>. Click Open to review and act.
            </p>
          </div>
        </div>

        {queueLoading && (
          <div className="flex items-center gap-2 text-xs text-gray-400 py-6">
            <Loader2 size={14} className="animate-spin" /> Loading your cases…
          </div>
        )}
        {queueError && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            {queueError}. If you never set up the queue in the database, this
            list may stay empty.
          </p>
        )}

        {waitingList && !queueLoading && (
          <>
            {myCases.length === 0 ? (
              <p className="text-sm text-gray-500 py-6 text-center">
                No cases are currently assigned to you. Good moment for a break.
              </p>
            ) : (
              <div className="overflow-x-auto border border-gray-100 rounded-xl">
                <table className="w-full text-xs min-w-[680px]">
                  {tableHeader}
                  <tbody>
                    {myCases.map((row) => (
                      <QueueRow
                        key={row.id}
                        row={row}
                        isMyCase={true}
                        onOpen={() => setModalCaseId(row.id)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {/* Other cases in queue (team visibility) */}
      {waitingList && !queueLoading && otherCases.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm space-y-4">
          <div className="flex items-center gap-2">
            <Inbox size={16} className="text-gray-400" />
            <div>
              <h2 className="text-sm font-bold text-gray-800">
                Other cases in the tier queue
              </h2>
              <p className="text-xs text-gray-500">
                Waiting or assigned to teammates — visible for awareness.
              </p>
            </div>
          </div>
          <div className="overflow-x-auto border border-gray-100 rounded-xl">
            <table className="w-full text-xs min-w-[680px]">
              {tableHeader}
              <tbody>
                {otherCases.map((row) => (
                  <QueueRow
                    key={row.id}
                    row={row}
                    isMyCase={false}
                    onOpen={() => setModalCaseId(row.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Case detail modal */}
      {modalCaseId && (
        <CaseDetailModal
          caseId={modalCaseId}
          staffId={staffId}
          supportLevel={supportLevel}
          onClose={() => setModalCaseId(null)}
          onActionComplete={refreshAll}
        />
      )}
    </div>
  );
}

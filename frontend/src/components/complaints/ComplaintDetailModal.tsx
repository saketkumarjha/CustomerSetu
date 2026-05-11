import { useState, useEffect } from "react";
import {
  X,
  Bot,
  Send,
  Loader2,
  ChevronDown,
  ChevronUp,
  User,
  FileText,
  CheckCircle2,
  Clock,
  Shield,
  AlertTriangle,
} from "lucide-react";
import type { Complaint } from "../../types";
import type { ApiComplaint, AgentDecision } from "../../lib/api";
import { SeverityBadge } from "../ui/SeverityBadge";
import { ChannelBadge } from "../ui/ChannelBadge";
import { StatusBadge } from "../ui/StatusBadge";
import { SlaBadge } from "../ui/SlaBadge";
import { api } from "../../lib/api";
import { EscalationStatusSection } from "./detail/EscalationStatusSection";
import { ShadowOverrideSection } from "./detail/ShadowOverrideSection";

interface Props {
  complaint: Complaint;
  apiDetail: ApiComplaint | null;
  loadingDetail: boolean;
  pipelineAvailable: boolean;
  onClose: () => void;
  onAfterRunPipeline?: () => void;
  onComplaintUpdated?: () => void;
}

// ── Small helpers ─────────────────────────────────────────────────────────────

/** Render a value that might be null/undefined as a styled pill */
function Val({
  v,
  mono = false,
}: {
  v: string | number | boolean | null | undefined;
  mono?: boolean;
}) {
  if (v === null || v === undefined || v === "" || v === "—") {
    return <span className="text-slate-300 text-[11px] italic">—</span>;
  }
  if (typeof v === "boolean") {
    return (
      <span
        className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${
          v
            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
            : "bg-slate-100 text-slate-500 border border-slate-200"
        }`}
      >
        {v ? "Yes" : "No"}
      </span>
    );
  }
  return (
    <span
      className={`font-semibold text-slate-800 ${mono ? "font-mono text-[11px]" : ""}`}
    >
      {String(v)}
    </span>
  );
}

/** A labelled stat cell used in the analysis grid */
function StatCell({
  label,
  children,
  wide = false,
}: {
  label: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={`${wide ? "col-span-2" : ""} space-y-0.5`}>
      <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wide">
        {label}
      </div>
      <div className="text-xs">{children}</div>
    </div>
  );
}

/** Confidence bar — coloured fill */
function ConfBar({ value }: { value: number | null | undefined }) {
  if (value == null) return <Val v={null} />;
  const pct = Math.round(value * 100);
  const colour =
    pct >= 80 ? "bg-emerald-500" : pct >= 60 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${colour}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span
        className={`font-semibold text-xs ${pct >= 80 ? "text-emerald-600" : pct >= 60 ? "text-amber-600" : "text-red-500"}`}
      >
        {pct}%
      </span>
    </div>
  );
}

/** Route pill */
function RoutePill({ route }: { route: string | null | undefined }) {
  if (!route) return <Val v={null} />;
  const r = route.toUpperCase();
  const styles =
    r === "AUTO" || r === "AUTO_RESPOND"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : r === "ESCALATE"
        ? "bg-violet-50 text-violet-700 border-violet-200"
        : r === "HUMAN" || r === "HUMAN_REVIEW"
          ? "bg-amber-50 text-amber-700 border-amber-200"
          : "bg-slate-50 text-slate-600 border-slate-200";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${styles}`}
    >
      {route}
    </span>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ComplaintDetailModal({
  complaint,
  apiDetail,
  loadingDetail,
  pipelineAvailable: _pipelineAvailable,
  onClose,
  onAfterRunPipeline: _onAfterRunPipeline,
  onComplaintUpdated: _onComplaintUpdated,
}: Props) {
  const [draft, setDraft] = useState("");
  const [agentDecisions, setAgentDecisions] = useState<AgentDecision[]>([]);
  const [showFullDetail, setShowFullDetail] = useState(false);
  const [showDecisions, setShowDecisions] = useState(false);

  useEffect(() => {
    const res = complaint.agentResult.resolution;
    setDraft(res && res !== "—" ? res : "");
    setAgentDecisions([]);
    setShowFullDetail(false);
    setShowDecisions(false);
  }, [complaint.id, complaint.agentResult.resolution]);

  useEffect(() => {
    if (!apiDetail || apiDetail.pipeline_status !== "complete") return;
    api.complaints
      .explanation(apiDetail.complaint_id)
      .then((r) => setAgentDecisions(r.explanation_trace))
      .catch(() => {});
  }, [apiDetail?.complaint_id, apiDetail?.pipeline_status]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const hasDraft = !!draft;
  const pipelineComplete = apiDetail?.pipeline_status === "complete";
  const hasAnalysis = pipelineComplete || !!apiDetail?.category;

  const detailFields = apiDetail
    ? Object.entries(apiDetail).filter(([k, v]) => {
        if (k === "embedding") return false;
        if (typeof v === "object" && v !== null) return false;
        return true;
      })
    : [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      <div
        className="relative bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 py-4 bg-ub-blue flex-shrink-0">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-white font-bold text-sm font-mono tracking-wide">
                {complaint.id}
              </span>
              <StatusBadge status={complaint.status} />
              {pipelineComplete && (
                <span className="text-[11px] bg-white/15 text-white px-2 py-0.5 rounded-full border border-white/20 flex items-center gap-1">
                  <CheckCircle2 size={9} /> Analysis complete
                </span>
              )}
              {loadingDetail && (
                <Loader2 size={12} className="text-blue-200 animate-spin" />
              )}
            </div>
            <div className="text-blue-200/70 text-xs mt-1 truncate">
              {complaint.category} · {complaint.channel} · {complaint.date}
            </div>
          </div>
          <button
            onClick={onClose}
            className="ml-3 w-8 h-8 rounded-lg bg-white/15 text-white flex items-center justify-center hover:bg-white/25 transition-colors flex-shrink-0"
            aria-label="Close"
          >
            <X size={15} />
          </button>
        </div>

        {/* ── Body ── */}
        <div className="overflow-y-auto flex-1 p-4 sm:p-5 space-y-4 bg-slate-50/40">
          {/* ── Row 1: Customer card + Complaint text ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Customer card */}
            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 shadow-sm">
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                <User size={10} /> Customer
              </div>
              <div>
                <div className="font-bold text-sm text-slate-800 break-all leading-snug">
                  {complaint.customer}
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1">
                  <Clock size={9} /> {complaint.date} {complaint.time}
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <ChannelBadge channel={complaint.channel} />
                <SeverityBadge severity={complaint.severity} />
                <SlaBadge
                  breached={complaint.slaBreached}
                  label={complaint.slaRemaining}
                />
              </div>
              {/* Tier info */}
              {apiDetail?.assigned_tier != null && (
                <div className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2 text-xs space-y-1">
                  <div className="text-[10px] text-slate-400 uppercase tracking-wide">
                    Routing
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-700">
                      Tier {apiDetail.assigned_tier}
                    </span>
                    {apiDetail.current_tier != null &&
                      apiDetail.current_tier !== apiDetail.assigned_tier && (
                        <span className="text-slate-400 text-[11px]">
                          (was {apiDetail.current_tier})
                        </span>
                      )}
                  </div>
                </div>
              )}
            </div>

            {/* Complaint text */}
            <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                <FileText size={10} /> Complaint text
              </div>
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                {complaint.description && complaint.description !== "—" ? (
                  complaint.description
                ) : (
                  <span className="text-slate-300 italic">
                    No text available
                  </span>
                )}
              </p>
              {apiDetail?.language && apiDetail.language !== "en" && (
                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-slate-500 bg-slate-50 border border-slate-100 rounded-lg px-2.5 py-1.5">
                  <span className="font-semibold uppercase">
                    {apiDetail.language}
                  </span>
                  <span className="text-slate-300">·</span>
                  <span>auto-translated</span>
                </div>
              )}
              {apiDetail?.is_duplicate && (
                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-2.5 py-1.5">
                  <AlertTriangle size={11} />
                  Possible duplicate of{" "}
                  {apiDetail.duplicate_of ?? "another complaint"}
                </div>
              )}
            </div>
          </div>

          {/* ── Shadow override ── */}
          {apiDetail &&
            (apiDetail.status === "shadow_sent" ||
              apiDetail.shadow_overridden) && (
              <ShadowOverrideSection
                apiDetail={apiDetail}
                onApplied={() => _onComplaintUpdated?.()}
              />
            )}

          {/* ── Row 2: AI Analysis + Draft Response ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* AI Analysis */}
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-4">
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                <Bot size={10} /> AI Analysis
              </div>

              {!hasAnalysis ? (
                <div className="flex flex-col items-center justify-center py-8 gap-2 text-center">
                  <Bot size={28} className="text-slate-200" />
                  <p className="text-xs text-slate-400">
                    {apiDetail?.pipeline_status === "processing"
                      ? "Pipeline is running…"
                      : "No analysis yet for this complaint."}
                  </p>
                </div>
              ) : (
                <>
                  {/* Scores grid */}
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <StatCell label="Category">
                      <Val v={apiDetail?.category ?? complaint.category} />
                    </StatCell>
                    <StatCell label="Sentiment">
                      <Val v={apiDetail?.sentiment ?? complaint.sentiment} />
                    </StatCell>
                    <StatCell label="Urgency">
                      <Val
                        v={
                          apiDetail?.urgency_score != null
                            ? `${apiDetail.urgency_score}/10`
                            : null
                        }
                      />
                    </StatCell>
                    <StatCell label="Severity">
                      <Val
                        v={
                          apiDetail?.severity != null
                            ? `${apiDetail.severity}/5`
                            : null
                        }
                      />
                    </StatCell>
                    <StatCell label="Confidence" wide>
                      <ConfBar value={apiDetail?.confidence_score} />
                    </StatCell>
                    <StatCell label="Grounding">
                      <ConfBar value={apiDetail?.grounding_score} />
                    </StatCell>
                    <StatCell label="Risk Score">
                      <ConfBar value={apiDetail?.risk_score} />
                    </StatCell>
                    <StatCell label="Route">
                      <RoutePill route={apiDetail?.route} />
                    </StatCell>
                    <StatCell label="Compliance" wide>
                      <div className="flex items-center gap-2 flex-wrap">
                        <Val
                          v={
                            apiDetail?.compliance_category?.replace(
                              /_/g,
                              " ",
                            ) ?? null
                          }
                        />
                        {apiDetail?.is_rbi_reportable && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-50 text-red-600 border border-red-200">
                            <Shield size={9} /> RBI Reportable
                          </span>
                        )}
                      </div>
                    </StatCell>
                  </div>

                  {/* Root cause */}
                  {apiDetail?.root_cause ? (
                    <div className="rounded-lg bg-slate-50 border border-slate-100 p-3 space-y-1">
                      <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">
                        Root Cause
                      </div>
                      <p className="text-xs text-slate-700 leading-relaxed">
                        {apiDetail.root_cause}
                      </p>
                    </div>
                  ) : null}

                  {/* Action steps */}
                  {apiDetail?.action_steps &&
                    apiDetail.action_steps.length > 0 && (
                      <div className="rounded-lg bg-slate-50 border border-slate-100 p-3 space-y-1.5">
                        <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">
                          Action Steps
                        </div>
                        <ol className="space-y-1">
                          {apiDetail.action_steps.map((s, i) => (
                            <li
                              key={i}
                              className="flex gap-2 text-xs text-slate-700"
                            >
                              <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ub-blue/10 text-ub-blue text-[10px] font-bold flex items-center justify-center mt-0.5">
                                {i + 1}
                              </span>
                              <span className="leading-snug">{s}</span>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                </>
              )}
            </div>

            {/* Draft Response */}
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-3">
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                <Send size={10} /> Draft Response
              </div>

              {hasDraft ? (
                <div className="space-y-3">
                  <textarea
                    value={draft}
                    readOnly
                    rows={9}
                    className="w-full text-xs text-slate-700 border border-slate-200 rounded-lg p-3 resize-none focus:outline-none leading-relaxed bg-slate-50/50 cursor-default select-text"
                  />
                  {apiDetail?.confidence_score != null && (
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-slate-400">Confidence:</span>
                      <ConfBar value={apiDetail.confidence_score} />
                      {apiDetail.confidence_score >= 0.8 && (
                        <span className="text-emerald-600 font-medium text-[11px]">
                          High confidence
                        </span>
                      )}
                    </div>
                  )}
                  <p className="text-[11px] text-slate-400 text-center">
                    Use the Agent Desk tab to Accept, Edit, or Escalate this
                    draft.
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 gap-2 text-center">
                  <Send size={28} className="text-slate-200" />
                  <p className="text-xs text-slate-400">
                    No draft generated yet.
                  </p>
                  <p className="text-[11px] text-slate-300">
                    Run the pipeline from the Pipeline tab to generate a
                    response.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* ── Agent Decisions Trace ── */}
          {agentDecisions.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              <button
                onClick={() => setShowDecisions((v) => !v)}
                className="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <Bot size={11} className="text-ub-blue" />
                  Agent Decisions
                  <span className="ml-1 px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500 text-[10px] font-bold">
                    {agentDecisions.length}
                  </span>
                </span>
                {showDecisions ? (
                  <ChevronUp size={14} />
                ) : (
                  <ChevronDown size={14} />
                )}
              </button>
              {showDecisions && (
                <div className="px-4 pb-4 space-y-2 border-t border-slate-100">
                  <div className="pt-3 space-y-2">
                    {agentDecisions.map((d, i) => (
                      <div
                        key={i}
                        className={`rounded-lg p-3 border text-xs ${
                          d.status === "failed"
                            ? "border-red-200 bg-red-50/60"
                            : "border-slate-100 bg-slate-50/60"
                        }`}
                      >
                        <div className="flex justify-between items-start mb-1.5">
                          <span
                            className={`font-semibold flex items-center gap-1.5 ${d.status === "failed" ? "text-red-700" : "text-slate-800"}`}
                          >
                            <span
                              className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0 ${
                                d.status === "failed"
                                  ? "bg-red-100 text-red-600"
                                  : "bg-ub-blue/10 text-ub-blue"
                              }`}
                            >
                              {d.agent_order ?? i + 1}
                            </span>
                            {d.agent_name}
                          </span>
                          <div className="flex items-center gap-2 text-slate-400 flex-shrink-0 ml-2">
                            {d.confidence != null && (
                              <span
                                className={`font-semibold ${d.confidence >= 0.8 ? "text-emerald-600" : "text-amber-500"}`}
                              >
                                {Math.round(d.confidence * 100)}%
                              </span>
                            )}
                            {d.duration_ms != null && (
                              <span className="flex items-center gap-0.5 text-[10px]">
                                <Clock size={9} />
                                {d.duration_ms}ms
                              </span>
                            )}
                          </div>
                        </div>
                        {d.decision && (
                          <p className="text-slate-700 font-medium leading-snug">
                            {d.decision}
                          </p>
                        )}
                        {d.reasoning && (
                          <p className="text-slate-500 mt-1 leading-relaxed text-[11px]">
                            {d.reasoning}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Escalation status ── */}
          <EscalationStatusSection
            complaintId={apiDetail?.complaint_id}
            enabled={!!apiDetail}
          />

          {/* ── Full backend detail ── */}
          {apiDetail && (
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              <button
                onClick={() => setShowFullDetail((v) => !v)}
                className="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-slate-500 hover:bg-slate-50 transition-colors"
              >
                <span>Raw backend fields ({detailFields.length})</span>
                {showFullDetail ? (
                  <ChevronUp size={14} />
                ) : (
                  <ChevronDown size={14} />
                )}
              </button>
              {showFullDetail && (
                <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-4">
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-3 text-xs">
                    {detailFields.map(([k, v]) => (
                      <div key={k}>
                        <div className="text-[10px] text-slate-400 font-mono mb-0.5">
                          {k}
                        </div>
                        <Val v={v as string | boolean | null} mono />
                      </div>
                    ))}
                  </div>
                  {apiDetail.action_steps &&
                    apiDetail.action_steps.length > 0 && (
                      <div>
                        <div className="text-[10px] text-slate-400 font-mono mb-1">
                          action_steps
                        </div>
                        <ol className="list-decimal pl-4 space-y-0.5 text-xs text-slate-700">
                          {apiDetail.action_steps.map((s, i) => (
                            <li key={i}>{s}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                  {apiDetail.grounding_warnings &&
                    apiDetail.grounding_warnings.length > 0 && (
                      <div>
                        <div className="text-[10px] text-slate-400 font-mono mb-1">
                          grounding_warnings
                        </div>
                        <pre className="text-xs text-slate-700 bg-slate-50 rounded-lg p-2 border border-slate-100 overflow-auto max-h-40 leading-relaxed">
                          {JSON.stringify(
                            apiDetail.grounding_warnings,
                            null,
                            2,
                          )}
                        </pre>
                      </div>
                    )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

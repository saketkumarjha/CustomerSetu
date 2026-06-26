import { useState, useEffect } from "react";
import {
  X,
  Bot,
  BookOpen,
  ChevronDown,
  ChevronUp,
  User,
  FileText,
  CheckCircle2,
  Clock,
  Shield,
  TrendingUp,
  Activity,
  Layers,
  Info,
} from "lucide-react";
import type { Complaint } from "../../types";
import type { ApiComplaint, AgentDecision, GroundingWarningItem } from "../../lib/api";
import { SeverityBadge } from "../ui/SeverityBadge";
import { ChannelBadge } from "../ui/ChannelBadge";
import { StatusBadge } from "../ui/StatusBadge";
import { SlaBadge } from "../ui/SlaBadge";
import { api } from "../../lib/api";
import { EscalationStatusSection } from "./detail/EscalationStatusSection";
import { ShadowOverrideSection } from "./detail/ShadowOverrideSection";
import { DuplicateBanner } from "./DuplicateBanner";
import { CustomerSummaryCard } from "../customers/CustomerSummaryCard";

interface Props {
  complaint: Complaint;
  apiDetail: ApiComplaint | null;
  loadingDetail: boolean;
  pipelineAvailable: boolean;
  onClose: () => void;
  onAfterRunPipeline?: () => void;
  onComplaintUpdated?: () => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Null-safe value renderer */
function Val({
  v,
  mono = false,
}: {
  v: string | number | boolean | null | undefined;
  mono?: boolean;
}) {
  if (v === null || v === undefined || v === "" || v === "—") {
    return <span className="text-slate-300 italic text-[11px]">—</span>;
  }
  if (typeof v === "boolean") {
    return (
      <span
        className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${
          v
            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
            : "bg-slate-100 text-slate-400 border border-slate-200"
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

/** Labelled stat cell */
function Cell({
  label,
  children,
  wide = false,
}: {
  label: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={`${wide ? "col-span-2" : ""} space-y-1`}>
      <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
        {label}
      </div>
      <div className="text-xs">{children}</div>
    </div>
  );
}

/** Confidence bar */
function ConfBar({ value }: { value: number | null | undefined }) {
  if (value == null) return <Val v={null} />;
  const pct = Math.round(value * 100);
  const colour =
    pct >= 80 ? "bg-emerald-500" : pct >= 60 ? "bg-amber-400" : "bg-red-400";
  const textColour =
    pct >= 80
      ? "text-emerald-600"
      : pct >= 60
        ? "text-amber-600"
        : "text-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${colour}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`font-semibold text-xs tabular-nums ${textColour}`}>
        {pct}%
      </span>
    </div>
  );
}

// ── Grounding helpers ─────────────────────────────────────────────────────────

function GroundingWarningRow({ w }: { w: string | GroundingWarningItem }) {
  if (typeof w === "string") return <li className="text-slate-600">{w}</li>;
  const title = [w.type, w.claim].filter(Boolean).join(" — ");
  return (
    <li className="text-slate-600 border-l-2 border-amber-400/70 pl-2 py-1.5 space-y-0.5">
      {title && <div className="font-medium text-slate-800">{title}</div>}
      {w.issue && <div><span className="text-slate-400">Issue: </span>{w.issue}</div>}
      {w.suggestion && <div className="text-slate-500"><span className="text-slate-400">Suggestion: </span>{w.suggestion}</div>}
    </li>
  );
}

type GroundingStatus = "skipped" | "passed" | "warnings" | "failed";

function deriveGroundingStatus(
  score: number | null | undefined,
  warnings: (string | GroundingWarningItem)[] | undefined,
): GroundingStatus {
  if (score === null || score === undefined) return "skipped";
  if (
    score === 0.0 &&
    (warnings ?? []).some(
      (w) => typeof w === "object" && (w as GroundingWarningItem).type === "SYSTEM_ERROR",
    )
  ) return "failed";
  if ((warnings ?? []).length > 0) return "warnings";
  return "passed";
}

function buildWarningSummary(warnings: (string | GroundingWarningItem)[]): string[] {
  const counts: Record<string, number> = {};
  for (const w of warnings) {
    if (typeof w === "object" && (w as GroundingWarningItem).type) {
      const t = (w as GroundingWarningItem).type!;
      counts[t] = (counts[t] ?? 0) + 1;
    }
  }
  const lines: string[] = [];
  if (counts["UNVERIFIABLE_CLAIM"])
    lines.push(`${counts["UNVERIFIABLE_CLAIM"]} unsupported claim${counts["UNVERIFIABLE_CLAIM"] > 1 ? "s" : ""} detected.`);
  if (counts["RBI_COMPLIANCE"])
    lines.push(`${counts["RBI_COMPLIANCE"]} RBI compliance issue${counts["RBI_COMPLIANCE"] > 1 ? "s" : ""} found.`);
  if (counts["AUTHORITY_EXCEEDED"])
    lines.push(`${counts["AUTHORITY_EXCEEDED"]} authority violation${counts["AUTHORITY_EXCEEDED"] > 1 ? "s" : ""} detected.`);
  return lines;
}

/** Route status pill */
function RouteStatusPill({
  route,
  status,
}: {
  route?: string | null;
  status?: string | null;
}) {
  const r = (route ?? "").toLowerCase();
  const s = (status ?? "").toLowerCase();

  if (
    r === "auto_respond" ||
    r === "auto" ||
    s === "auto_respond" ||
    s === "auto_closed" ||
    s === "resolved" ||
    s === "awaiting_feedback"
  ) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Auto Sent
      </span>
    );
  }
  if (
    r === "human_review" ||
    r === "human" ||
    s === "human_review" ||
    s === "pending_review" ||
    s === "in_review"
  ) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Human Review
      </span>
    );
  }
  if (r === "escalate" || r === "escalated" || s === "escalated") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-violet-50 text-violet-700 border border-violet-200">
        <span className="w-1.5 h-1.5 rounded-full bg-violet-500" /> Escalated
      </span>
    );
  }
  if (s === "shadow_sent") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-orange-50 text-orange-700 border border-orange-200">
        <span className="w-1.5 h-1.5 rounded-full bg-orange-500" /> Shadow Sent
      </span>
    );
  }
  if (s === "processing") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />{" "}
        Processing
      </span>
    );
  }
  return null;
}

/** Section card wrapper */
function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden ${className}`}
    >
      {children}
    </div>
  );
}

/** Section header inside a card */
function CardHeader({
  icon,
  title,
  right,
}: {
  icon: React.ReactNode;
  title: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50/60">
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 uppercase tracking-wider">
        <span className="text-slate-400">{icon}</span>
        {title}
      </div>
      {right && <div>{right}</div>}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ComplaintDetailModal({
  complaint,
  apiDetail,
  loadingDetail,
  onClose,
  onComplaintUpdated,
}: Props) {
  const [agentDecisions, setAgentDecisions] = useState<AgentDecision[]>([]);
  const [showDecisions, setShowDecisions] = useState(false);
  const [showRawFields, setShowRawFields] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    setAgentDecisions([]);
    setShowDecisions(false);
    setShowRawFields(false);
  }, [complaint.id]);

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

  const draft = apiDetail?.draft_response ?? complaint.agentResult.resolution;
  const hasDraft = !!draft && draft !== "—";
  const pipelineComplete = apiDetail?.pipeline_status === "complete";
  const hasAnalysis = pipelineComplete || !!apiDetail?.category;

  const rawFields = apiDetail
    ? Object.entries(apiDetail).filter(([k, v]) => {
        if (k === "embedding") return false;
        if (typeof v === "object" && v !== null) return false;
        if (v === null || v === undefined || v === "") return false;
        return true;
      })
    : [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />

      {/* Modal — scale-in entrance */}
      <div
        className="relative bg-slate-50 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden"
        style={{ animation: "modalIn 0.2s cubic-bezier(0.16,1,0.3,1) both" }}
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
              {apiDetail && (
                <RouteStatusPill
                  route={apiDetail.route}
                  status={apiDetail.status}
                />
              )}
              {pipelineComplete && (
                <span className="text-[11px] bg-white/15 text-white px-2 py-0.5 rounded-full border border-white/20 flex items-center gap-1">
                  <CheckCircle2 size={9} /> Analysis complete
                </span>
              )}
              {loadingDetail && (
                <span className="text-[11px] bg-white/10 text-blue-200 px-2 py-0.5 rounded-full border border-white/15 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-300 animate-pulse" />{" "}
                  Loading…
                </span>
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
        <div className="overflow-y-auto flex-1 p-4 sm:p-5 space-y-4">
          {/* Row 1: Customer + Complaint text */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Customer card */}
            <Card>
              <CardHeader icon={<User size={12} />} title="Customer" />
              <div className="p-4 space-y-3">
                {/* Avatar + name */}
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-ub-blue to-blue-700 text-white flex items-center justify-center font-bold text-sm flex-shrink-0 shadow-sm">
                    {complaint.customer.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <div className="font-semibold text-sm text-slate-800 leading-tight">
                      {complaint.customer}
                    </div>
                    <div className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                      <Clock size={9} /> {complaint.date} {complaint.time}
                    </div>
                  </div>
                </div>

                {/* Badges */}
                <div className="flex flex-wrap gap-1.5">
                  <ChannelBadge channel={complaint.channel} />
                  <SeverityBadge severity={complaint.severity} />
                  <SlaBadge
                    breached={complaint.slaBreached}
                    label={complaint.slaRemaining}
                  />
                </div>

                {/* Tier routing */}
                {apiDetail?.assigned_tier != null && (
                  <div className="rounded-xl bg-slate-50 border border-slate-100 px-3 py-2.5 space-y-1.5">
                    <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                      Routing
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-slate-700 text-xs">
                        Tier {apiDetail.assigned_tier}
                      </span>
                      {apiDetail.current_tier != null &&
                        apiDetail.current_tier !== apiDetail.assigned_tier && (
                          <span className="text-slate-400 text-[11px]">
                            (escalated from {apiDetail.current_tier})
                          </span>
                        )}
                    </div>
                  </div>
                )}

                {/* Customer History — collapsible, inside Customer card */}
                {apiDetail?.cif_id && (
                  <div className="border border-slate-100 rounded-xl overflow-hidden">
                    <button
                      className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 hover:bg-slate-100 text-xs font-semibold text-slate-600 transition-colors"
                      onClick={() => setShowHistory(h => !h)}
                    >
                      <span className="flex items-center gap-1.5">
                        <BookOpen size={11} className="text-ub-blue" />
                        Customer History
                      </span>
                      {showHistory ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    </button>
                    {showHistory && (
                      <div className="p-3">
                        <CustomerSummaryCard cifId={apiDetail.cif_id} />
                      </div>
                    )}
                  </div>
                )}

                {/* Duplicate banner with merge/confirm actions */}
                {apiDetail?.duplicate_status &&
                  apiDetail.duplicate_status !== 'merged' &&
                  (apiDetail.duplicate_of?.length ?? 0) > 0 && (
                  <DuplicateBanner
                    complaintId={apiDetail.complaint_id}
                    duplicateStatus={apiDetail.duplicate_status}
                    duplicateOf={apiDetail.duplicate_of ?? []}
                    ownCifId={apiDetail.cif_id}
                    ownChannel={apiDetail.channel}
                    ownText={apiDetail.masked_text ?? apiDetail.original_text}
                    onActionComplete={() => onComplaintUpdated?.()}
                  />
                )}
              </div>
            </Card>

            {/* Complaint text */}
            <Card>
              <CardHeader
                icon={<FileText size={12} />}
                title="Complaint Text"
                right={
                  apiDetail?.language && apiDetail.language !== "en" ? (
                    <span className="text-[10px] bg-slate-100 text-slate-500 border border-slate-200 px-2 py-0.5 rounded-full font-semibold uppercase">
                      {apiDetail.language} · translated
                    </span>
                  ) : undefined
                }
              />
              <div className="p-4">
                <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                  {complaint.description && complaint.description !== "—" ? (
                    complaint.description
                  ) : (
                    <span className="text-slate-300 italic">
                      No text available
                    </span>
                  )}
                </p>
              </div>
            </Card>
          </div>

          {/* Shadow override */}
          {apiDetail &&
            (apiDetail.status === "shadow_sent" ||
              apiDetail.shadow_overridden) && (
              <ShadowOverrideSection
                apiDetail={apiDetail}
                onApplied={() => onComplaintUpdated?.()}
              />
            )}

          {/* Row 2: AI Analysis + Draft Response */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* AI Analysis */}
            <Card>
              <CardHeader icon={<Activity size={12} />} title="AI Analysis" />
              <div className="p-4">
                {!hasAnalysis ? (
                  <div className="flex flex-col items-center justify-center py-10 gap-3 text-center">
                    <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center">
                      <Bot size={22} className="text-slate-300" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-slate-500">
                        {apiDetail?.pipeline_status === "processing"
                          ? "Pipeline is running…"
                          : "No analysis yet"}
                      </p>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        Run the pipeline to generate AI analysis
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Scores grid */}
                    <div className="grid grid-cols-2 gap-x-5 gap-y-3">
                      {(apiDetail?.category ?? complaint.category) && (
                        <Cell label="Category">
                          <Val v={apiDetail?.category ?? complaint.category} />
                        </Cell>
                      )}
                      {(apiDetail?.sentiment ?? complaint.sentiment) && (
                        <Cell label="Sentiment">
                          <Val v={apiDetail?.sentiment ?? complaint.sentiment} />
                        </Cell>
                      )}
                      {apiDetail?.urgency_score != null && (
                        <Cell label="Urgency">
                          <Val v={`${apiDetail.urgency_score}/10`} />
                        </Cell>
                      )}
                      {apiDetail?.severity != null && (
                        <Cell label="Severity">
                          <Val v={`${apiDetail.severity}/5`} />
                        </Cell>
                      )}
                      {apiDetail?.confidence_score != null && (
                        <Cell label="Confidence" wide>
                          <ConfBar value={apiDetail.confidence_score} />
                        </Cell>
                      )}
                      {apiDetail?.risk_score != null && (
                        <Cell label="Risk Score">
                          <ConfBar value={apiDetail.risk_score} />
                        </Cell>
                      )}
                      {apiDetail?.route && (
                        <Cell label="Route">
                          <RouteStatusPill
                            route={apiDetail.route}
                            status={apiDetail.status}
                          />
                        </Cell>
                      )}
                    </div>

                    {/* Compliance */}
                    {(apiDetail?.compliance_category ||
                      apiDetail?.is_rbi_reportable) && (
                      <div
                        className={`rounded-xl px-3 py-2.5 border ${apiDetail?.is_rbi_reportable ? "bg-red-50 border-red-200" : "bg-slate-50 border-slate-200"}`}
                      >
                        <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                          <Shield size={10} /> Compliance
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-medium text-slate-700">
                            {apiDetail?.compliance_category?.replace(
                              /_/g,
                              " ",
                            ) ?? "—"}
                          </span>
                          {apiDetail?.is_rbi_reportable && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-100 text-red-700 border border-red-200">
                              <Shield size={9} /> RBI Reportable
                            </span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Root cause */}
                    {apiDetail?.root_cause && (
                      <div className="rounded-xl bg-slate-50 border border-slate-100 p-3 space-y-1">
                        <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                          Root Cause
                        </div>
                        <p className="text-xs text-slate-700 leading-relaxed">
                          {apiDetail.root_cause}
                        </p>
                      </div>
                    )}

                    {/* Action steps */}
                    {apiDetail?.action_steps &&
                      apiDetail.action_steps.length > 0 && (
                        <div className="rounded-xl bg-slate-50 border border-slate-100 p-3 space-y-2">
                          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                            Action Steps
                          </div>
                          <ol className="space-y-1.5">
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

                  </div>
                )}
              </div>
            </Card>

            {/* Draft Response — read-only */}
            <Card>
              <CardHeader
                icon={<TrendingUp size={12} />}
                title="Draft Response"
                right={
                  <span className="text-[10px] bg-slate-100 text-slate-500 border border-slate-200 px-2 py-0.5 rounded-full font-semibold flex items-center gap-1">
                    <Info size={9} /> Read-only
                  </span>
                }
              />
              <div className="p-4 space-y-3">
                {hasDraft ? (
                  <>
                    <div className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap bg-slate-50/80 border border-slate-100 rounded-xl p-3 select-text min-h-[160px]">
                      {draft}
                    </div>
                    {apiDetail?.confidence_score != null && (
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <span className="flex-shrink-0">Confidence:</span>
                        <ConfBar value={apiDetail.confidence_score} />
                      </div>
                    )}
                    <div className="flex items-start gap-2 rounded-xl bg-blue-50 border border-blue-100 px-3 py-2.5">
                      <Info
                        size={12}
                        className="text-blue-400 flex-shrink-0 mt-0.5"
                      />
                      <p className="text-[11px] text-blue-700 leading-relaxed">
                        To Accept, Edit, or Escalate this draft, go to the{" "}
                        <strong>Agent Desk</strong> tab.
                      </p>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-col items-center justify-center py-10 gap-3 text-center">
                    <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center">
                      <TrendingUp size={22} className="text-slate-300" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-slate-500">
                        No draft generated yet
                      </p>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        Run the pipeline to generate a response
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Grounding Check */}
          {apiDetail && (() => {
            const gStatus = deriveGroundingStatus(
              apiDetail.grounding_score,
              apiDetail.grounding_warnings,
            );
            const nonSystemWarnings = (apiDetail.grounding_warnings ?? []).filter(
              (w) => !(typeof w === "object" && (w as GroundingWarningItem).type === "SYSTEM_ERROR"),
            );
            const warningSummary = buildWarningSummary(nonSystemWarnings);
            const badgeClass =
              gStatus === "passed"
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : gStatus === "warnings"
                  ? "bg-amber-50 text-amber-700 border-amber-200"
                  : gStatus === "failed"
                    ? "bg-red-50 text-red-700 border-red-200"
                    : "bg-slate-100 text-slate-500 border-slate-200";
            const badgeLabel =
              gStatus === "passed"
                ? "✅ Passed"
                : gStatus === "warnings"
                  ? "⚠ Warnings Found"
                  : gStatus === "failed"
                    ? "✗ Failed"
                    : "⊘ Not Executed";
            return (
              <Card>
                <CardHeader icon={<Shield size={12} />} title="Grounding Check"
                  right={
                    <div className="flex items-center gap-2">
                      {gStatus === "warnings" && apiDetail.grounding_score != null && (
                        <span className="text-xs text-slate-500">
                          {Math.round(apiDetail.grounding_score * 100)}%
                        </span>
                      )}
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${badgeClass}`}>
                        {badgeLabel}
                      </span>
                    </div>
                  }
                />
                <div className="p-4 text-xs text-slate-700 space-y-2">
                  {gStatus === "passed" && (
                    <ul className="space-y-1 text-slate-600">
                      <li>• No unsupported or unverifiable claims were detected.</li>
                      <li>• The response is consistent with the complaint context.</li>
                      <li>• No RBI compliance issues were found.</li>
                      <li>• The AI did not exceed its authority or make unsupported commitments.</li>
                    </ul>
                  )}
                  {gStatus === "warnings" && (
                    <div className="space-y-2">
                      <ul className="space-y-0.5 text-slate-600">
                        {warningSummary.map((line, i) => <li key={i}>• {line}</li>)}
                      </ul>
                      {nonSystemWarnings.length > 0 && (
                        <ul className="space-y-1">
                          {nonSystemWarnings.map((w, i) => <GroundingWarningRow key={i} w={w} />)}
                        </ul>
                      )}
                    </div>
                  )}
                  {gStatus === "skipped" && (
                    <p className="text-slate-600">
                      {apiDetail.is_duplicate === true
                        ? "Duplicate complaint detected. The pipeline ended before the grounding stage. No AI response was generated for validation."
                        : "The complaint was escalated or terminated before a draft response was generated."}
                    </p>
                  )}
                  {gStatus === "failed" && (
                    <ul className="space-y-1 text-slate-600">
                      <li>• The grounding service encountered an internal error.</li>
                      <li>• The AI response could not be validated.</li>
                      <li>• The complaint has been routed for human review.</li>
                    </ul>
                  )}
                </div>
              </Card>
            );
          })()}

          {/* Agent Decisions Trace */}
          {agentDecisions.length > 0 && (
            <Card>
              <button
                onClick={() => setShowDecisions((v) => !v)}
                className="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
              >
                <span className="flex items-center gap-2">
                  <Bot size={12} className="text-ub-blue" />
                  Agent Decision Trace
                  <span className="px-1.5 py-0.5 rounded-full bg-ub-blue/10 text-ub-blue text-[10px] font-bold">
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
                <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-2">
                  {agentDecisions.map((d, i) => (
                    <div
                      key={i}
                      className={`rounded-xl p-3 border text-xs ${
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
              )}
            </Card>
          )}

          {/* Escalation status */}
          <EscalationStatusSection
            complaintId={apiDetail?.complaint_id}
            enabled={!!apiDetail}
          />

          {/* Raw backend fields */}
          {apiDetail && rawFields.length > 0 && (
            <Card>
              <button
                onClick={() => setShowRawFields((v) => !v)}
                className="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-slate-500 hover:bg-slate-50 transition-colors"
              >
                <span className="flex items-center gap-2">
                  <Layers size={12} className="text-slate-400" />
                  Raw Backend Fields
                  <span className="px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500 text-[10px] font-bold">
                    {rawFields.length}
                  </span>
                </span>
                {showRawFields ? (
                  <ChevronUp size={14} />
                ) : (
                  <ChevronDown size={14} />
                )}
              </button>
              {showRawFields && (
                <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-4">
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-3 text-xs">
                    {rawFields.map(([k, v]) => (
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
                        <pre className="text-xs text-slate-700 bg-slate-50 rounded-xl p-3 border border-slate-100 overflow-auto max-h-40 leading-relaxed">
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
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

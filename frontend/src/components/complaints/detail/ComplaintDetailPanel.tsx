import { useState, useEffect } from "react";
import {
  X,
  User,
  MessageCircle,
  Copy,
  Shield,
  Loader2,
  Bot,
  Clock,
  CheckCircle2,
} from "lucide-react";
import type { Complaint } from "../../../types";
import type {
  ApiComplaint,
  AgentDecision,
  GroundingWarningItem,
} from "../../../lib/api";
import { SeverityBadge } from "../../ui/SeverityBadge";
import { ChannelBadge } from "../../ui/ChannelBadge";
import { SlaBadge } from "../../ui/SlaBadge";
import { getInitials, getActorColor } from "../../../utils/styles";
import { api } from "../../../lib/api";
import { EscalationStatusSection } from "./EscalationStatusSection";
import { ShadowOverrideSection } from "./ShadowOverrideSection";

function GroundingWarningRow({ w }: { w: string | GroundingWarningItem }) {
  if (typeof w === "string") {
    return <li className="text-slate-600">{w}</li>;
  }
  const title = [w.type, w.claim].filter(Boolean).join(" — ");
  return (
    <li className="text-slate-600 border-l-2 border-amber-400/70 pl-2 py-1.5 space-y-0.5">
      {title && <div className="font-medium text-slate-800">{title}</div>}
      {w.issue && (
        <div>
          <span className="text-slate-400">Issue: </span>
          {w.issue}
        </div>
      )}
      {w.suggestion && (
        <div className="text-slate-500">
          <span className="text-slate-400">Suggestion: </span>
          {w.suggestion}
        </div>
      )}
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
  )
    return "failed";
  if ((warnings ?? []).length > 0) return "warnings";
  return "passed";
}

function buildWarningSummary(
  warnings: (string | GroundingWarningItem)[],
): string[] {
  const counts: Record<string, number> = {};
  for (const w of warnings) {
    if (typeof w === "object" && (w as GroundingWarningItem).type) {
      const t = (w as GroundingWarningItem).type!;
      counts[t] = (counts[t] ?? 0) + 1;
    }
  }
  const lines: string[] = [];
  if (counts["UNVERIFIABLE_CLAIM"])
    lines.push(
      `${counts["UNVERIFIABLE_CLAIM"]} unsupported claim${counts["UNVERIFIABLE_CLAIM"] > 1 ? "s" : ""} detected.`,
    );
  if (counts["RBI_COMPLIANCE"])
    lines.push(
      `${counts["RBI_COMPLIANCE"]} RBI compliance issue${counts["RBI_COMPLIANCE"] > 1 ? "s" : ""} found.`,
    );
  if (counts["AUTHORITY_EXCEEDED"])
    lines.push(
      `${counts["AUTHORITY_EXCEEDED"]} authority violation${counts["AUTHORITY_EXCEEDED"] > 1 ? "s" : ""} detected.`,
    );
  return lines;
}

/** Route/status pill — maps backend values to a human-readable label */
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
    s === "auto_respond" ||
    s === "resolved" ||
    s === "awaiting_feedback"
  ) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        Auto Sent
      </span>
    );
  }
  if (r === "human_review" || s === "human_review") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
        Human Review
      </span>
    );
  }
  if (r === "escalate" || r === "escalated" || s === "escalated") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-violet-50 text-violet-700 border border-violet-200">
        <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
        Escalated
      </span>
    );
  }
  if (s === "shadow_sent") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-orange-50 text-orange-700 border border-orange-200">
        <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
        Shadow Sent
      </span>
    );
  }
  if (s === "processing") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
        Processing
      </span>
    );
  }
  return null;
}

interface Props {
  complaint: Complaint;
  onClose: () => void;
  loadingDetail?: boolean;
  apiDetail?: ApiComplaint | null;
  pipelineAvailable?: boolean;
  onAfterRunPipeline?: () => void;
  onComplaintUpdated?: () => void;
}

export function ComplaintDetailPanel({
  complaint,
  onClose,
  loadingDetail,
  apiDetail,
  pipelineAvailable: _pipelineAvailable = false,
  onAfterRunPipeline: _onAfterRunPipeline,
  onComplaintUpdated,
}: Props) {
  const [agentDecisions, setAgentDecisions] = useState<AgentDecision[]>([]);
  const [loadingExplanation, setLoadingExplanation] = useState(false);

  useEffect(() => {
    setAgentDecisions([]);
  }, [complaint.id]);

  useEffect(() => {
    if (!apiDetail || apiDetail.pipeline_status !== "complete") return;
    setLoadingExplanation(true);
    api.complaints
      .explanation(apiDetail.complaint_id)
      .then((r) => setAgentDecisions(r.explanation_trace))
      .catch(() => {})
      .finally(() => setLoadingExplanation(false));
  }, [apiDetail?.complaint_id, apiDetail?.pipeline_status]);

  const r = complaint.agentResult;
  const draft = r.resolution && r.resolution !== "—" ? r.resolution : null;

  return (
    <div className="w-full lg:w-[460px] lg:min-w-[460px] flex flex-col bg-white lg:border-l border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 bg-ub-blue flex-shrink-0">
        <div>
          <div className="text-white font-bold text-sm font-mono">
            {complaint.id}
          </div>
          <div className="text-blue-200/90 text-xs">Complaint detail</div>
        </div>
        <div className="flex items-center gap-2">
          {loadingDetail && (
            <Loader2 size={14} className="text-blue-200 animate-spin" />
          )}
          {/* Route/status pill in header */}
          {apiDetail && (
            <RouteStatusPill
              route={apiDetail.route}
              status={apiDetail.status}
            />
          )}
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-md bg-white/15 text-white flex items-center justify-center hover:bg-white/25 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="overflow-y-auto flex-1 p-4 space-y-4">
        {/* Customer info */}
        <section className="rounded-xl p-3 border border-slate-200/90 bg-white/70 backdrop-blur-sm">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
            <User size={11} /> Customer Details
          </div>
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-full bg-ub-blue text-white flex items-center justify-center font-bold text-xs flex-shrink-0">
              {getInitials(complaint.customer)}
            </div>
            <div>
              <div className="font-semibold text-sm text-gray-800">
                {complaint.customer}
              </div>
              {complaint.accountNo !== "—" && (
                <div className="text-xs text-gray-500">
                  {complaint.accountNo} · {complaint.branch}
                </div>
              )}
              {complaint.phone !== "—" && (
                <div className="text-xs text-gray-400">{complaint.phone}</div>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 mt-3 text-xs">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-gray-400">Channel: </span>
              <ChannelBadge channel={complaint.channel} />
            </div>
            <div>
              <span className="text-gray-400">Date: </span>
              <span className="font-medium">{complaint.date}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-gray-400">Severity: </span>
              <SeverityBadge severity={complaint.severity} />
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-gray-400">SLA: </span>
              <SlaBadge
                breached={complaint.slaBreached}
                label={complaint.slaRemaining}
              />
            </div>
          </div>
        </section>

        {/* Complaint text */}
        <section>
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Complaint Description
          </div>
          <p className="text-xs text-gray-700 leading-relaxed bg-gray-50 rounded-xl p-3 border border-gray-100">
            {complaint.description && complaint.description !== "—" ? (
              complaint.description
            ) : (
              <span className="text-slate-300 italic">
                No description available
              </span>
            )}
          </p>
          {apiDetail?.language && apiDetail.language !== "en" && (
            <p className="text-xs text-slate-600 mt-1 bg-slate-50 px-2 py-1 rounded-md border border-slate-200/80">
              Language: <strong>{apiDetail.language.toUpperCase()}</strong>{" "}
              (translated automatically)
            </p>
          )}
        </section>

        {/* Shadow override section */}
        {apiDetail &&
          (apiDetail.status === "shadow_sent" ||
            apiDetail.status === "override_closed" ||
            apiDetail.shadow_overridden) && (
            <ShadowOverrideSection
              apiDetail={apiDetail}
              onApplied={() => onComplaintUpdated?.()}
            />
          )}

        {/* AI Analysis */}
        <section>
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Bot size={11} /> Analysis
            {loadingExplanation && (
              <Loader2 size={10} className="animate-spin text-gray-400" />
            )}
          </div>

          {agentDecisions.length > 0 ? (
            <div className="space-y-2">
              {agentDecisions.map((d) => (
                <div
                  key={d.agent_name}
                  className={`rounded-md p-3 border text-xs ${
                    d.status === "complete"
                      ? "border-slate-200 bg-white/80"
                      : d.status === "failed"
                        ? "border-ub-red/30 bg-ub-red/5"
                        : "border-slate-200 bg-slate-50/80"
                  }`}
                >
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="font-semibold text-slate-800 flex items-center gap-1">
                      <CheckCircle2 size={10} className="text-slate-500" />
                      {d.agent_name}
                    </span>
                    <div className="flex items-center gap-2">
                      {d.confidence !== undefined && (
                        <span className="text-slate-500">
                          {Math.round(d.confidence * 100)}% confidence
                        </span>
                      )}
                      {d.duration_ms && (
                        <span className="text-gray-400 flex items-center gap-0.5">
                          <Clock size={9} /> {d.duration_ms}ms
                        </span>
                      )}
                    </div>
                  </div>
                  {d.decision && (
                    <p className="text-gray-800 font-medium">{d.decision}</p>
                  )}
                  {d.reasoning && (
                    <p className="text-gray-500 mt-1 leading-relaxed">
                      {d.reasoning}
                    </p>
                  )}
                  {d.evidence && d.evidence.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {d.evidence.map((ev) => (
                        <span
                          key={ev}
                          className="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded-md text-xs border border-slate-200/80"
                        >
                          {ev}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {/* Classification */}
              <div className="rounded-md p-3 border border-slate-200 bg-white/80">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-semibold text-slate-800">
                    Classification
                  </span>
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md border border-slate-200/80">
                    {r.classification.confidence}% confidence
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <div>
                    <span className="text-gray-400">Category: </span>
                    <span className="font-medium">
                      {r.classification.category}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Product: </span>
                    <span className="font-medium">
                      {r.classification.product}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-gray-400">Type: </span>
                    <span className="font-medium">{r.classification.type}</span>
                  </div>
                </div>
              </div>

              {/* Sentiment */}
              <div className="rounded-md p-3 border border-slate-200 bg-slate-50/50">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-semibold text-slate-800 flex items-center gap-1">
                    <MessageCircle size={11} /> Sentiment
                  </span>
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md border border-slate-200/80">
                    {r.sentiment.confidence}% confidence
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1 text-xs">
                  <div>
                    <span className="text-slate-500">Emotion: </span>
                    <span className="font-medium text-slate-800">
                      {r.sentiment.emotion}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500">Urgency: </span>
                    <span className="font-medium text-slate-800">
                      {r.sentiment.urgency}%
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500">Escalate: </span>
                    <span className="font-medium text-slate-800">
                      {r.sentiment.escalate ? "Yes" : "No"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Duplicate */}
              <div className="rounded-xl p-3 border border-gray-200 bg-gray-50">
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-xs font-bold text-gray-700 flex items-center gap-1">
                    <Copy size={11} /> Duplicate Check
                  </span>
                  <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">
                    {r.duplicate.confidence}% conf.
                  </span>
                </div>
                <div className="text-xs">
                  {r.duplicate.isDuplicate ? (
                    <span className="text-ub-red font-medium">
                      Possible duplicate — {r.duplicate.similar} similar case(s)
                    </span>
                  ) : r.duplicate.similar > 0 ? (
                    <span className="text-slate-700 font-medium">
                      {r.duplicate.similar} related case(s), not marked
                      duplicate
                    </span>
                  ) : (
                    <span className="text-slate-700 font-medium">
                      No duplicate match
                    </span>
                  )}
                </div>
              </div>

              {/* Compliance */}
              <div
                className={`rounded-md p-3 border ${r.compliance.flagged ? "border-ub-red/25 bg-ub-red/5" : "border-slate-200 bg-white/80"}`}
              >
                <div className="flex justify-between items-center mb-1.5">
                  <span
                    className={`text-xs font-semibold flex items-center gap-1 ${r.compliance.flagged ? "text-ub-red" : "text-slate-800"}`}
                  >
                    <Shield size={11} /> Compliance
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-md border ${r.compliance.flagged ? "bg-white border-ub-red/20 text-ub-red" : "bg-slate-100 border-slate-200 text-slate-600"}`}
                  >
                    {r.compliance.confidence}% confidence
                  </span>
                </div>
                <div
                  className={`text-xs font-medium ${r.compliance.flagged ? "text-ub-red" : "text-slate-700"}`}
                >
                  Risk: {r.compliance.risk} — {r.compliance.reason}
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Tier routing snapshot */}
        <EscalationStatusSection
          complaintId={apiDetail?.complaint_id}
          enabled={!!apiDetail}
        />

        {/* Grounding info — always rendered when apiDetail exists */}
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
            <section className="rounded-md p-3 border border-slate-200 bg-slate-50/80 text-xs text-slate-700">
              {/* Header row */}
              <div className="flex items-center justify-between mb-2">
                <div className="font-semibold text-slate-800">Grounding Check</div>
                <div className="flex items-center gap-2">
                  {gStatus === "passed" && (
                    <span className="text-slate-500">100%</span>
                  )}
                  {gStatus === "warnings" && apiDetail.grounding_score != null && (
                    <span className="text-slate-500">
                      {Math.round(apiDetail.grounding_score * 100)}%
                    </span>
                  )}
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${badgeClass}`}
                  >
                    {badgeLabel}
                  </span>
                </div>
              </div>

              {/* Passed */}
              {gStatus === "passed" && (
                <div className="space-y-1.5">
                  <div className="text-slate-500 font-medium">Why it passed</div>
                  <ul className="space-y-0.5 text-slate-600">
                    <li>• No unsupported or unverifiable claims were detected.</li>
                    <li>• The response is consistent with the complaint context.</li>
                    <li>• No RBI compliance issues were found.</li>
                    <li>• The AI did not exceed its authority or make unsupported commitments.</li>
                  </ul>
                </div>
              )}

              {/* Warnings Found */}
              {gStatus === "warnings" && (
                <div className="space-y-2">
                  <div>
                    <div className="text-slate-500 font-medium mb-1">
                      Why it needs verification
                    </div>
                    <ul className="space-y-0.5 text-slate-600">
                      {warningSummary.map((line, i) => (
                        <li key={i}>• {line}</li>
                      ))}
                    </ul>
                  </div>
                  {nonSystemWarnings.length > 0 && (
                    <div>
                      <div className="text-slate-500 font-medium mb-1">Details</div>
                      <ul className="space-y-1">
                        {nonSystemWarnings.map((w, i) => (
                          <GroundingWarningRow key={i} w={w} />
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Skipped */}
              {gStatus === "skipped" && (
                <div className="space-y-1.5">
                  <div className="text-slate-500 font-medium">Why it was skipped</div>
                  <p className="text-slate-600">
                    {apiDetail.is_duplicate === true
                      ? "Duplicate complaint detected. The pipeline ended before the grounding stage. No AI response was generated for validation."
                      : "The complaint was escalated or terminated before a draft response was generated."}
                  </p>
                </div>
              )}

              {/* Failed */}
              {gStatus === "failed" && (
                <div className="space-y-1.5">
                  <div className="text-slate-500 font-medium">Why it failed</div>
                  <ul className="space-y-0.5 text-slate-600">
                    <li>• The grounding service encountered an internal error.</li>
                    <li>• The AI response could not be validated.</li>
                    <li>• The complaint has been routed for human review.</li>
                  </ul>
                </div>
              )}
            </section>
          );
        })()}

        {/* Communication history */}
        {complaint.history.length > 0 && (
          <section>
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Timeline
            </div>
            <div className="relative pl-5">
              <div className="absolute left-2 top-1 bottom-1 w-px bg-gray-200" />
              {complaint.history.map((h, i) => (
                <div key={i} className="relative mb-3 last:mb-0">
                  <div
                    className="absolute -left-3 top-1.5 w-2.5 h-2.5 rounded-full border-2 border-white"
                    style={{ backgroundColor: getActorColor(h.actor) }}
                  />
                  <div className="text-xs">
                    <span className="font-semibold text-gray-700">
                      {h.actor}
                    </span>
                    <span className="text-gray-400 ml-2">{h.time}</span>
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">
                    {h.action}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* AI Draft Response — read-only, no action buttons */}
        {draft && apiDetail?.status !== "shadow_sent" && (
          <section>
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
                AI Draft Response
              </div>
              <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-md border border-slate-200/80 font-medium flex items-center gap-1">
                Read-only · use Agent Desk to act
              </span>
            </div>
            <div className="w-full text-xs text-gray-700 border border-gray-200 rounded-xl p-3 leading-relaxed bg-slate-50/60 whitespace-pre-wrap select-text">
              {draft}
            </div>
            {apiDetail?.confidence_score != null && (
              <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
                <span>Confidence:</span>
                <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden max-w-[120px]">
                  <div
                    className={`h-full rounded-full ${apiDetail.confidence_score >= 0.8 ? "bg-emerald-500" : apiDetail.confidence_score >= 0.6 ? "bg-amber-400" : "bg-red-400"}`}
                    style={{
                      width: `${Math.round(apiDetail.confidence_score * 100)}%`,
                    }}
                  />
                </div>
                <span
                  className={`font-semibold ${apiDetail.confidence_score >= 0.8 ? "text-emerald-600" : apiDetail.confidence_score >= 0.6 ? "text-amber-600" : "text-red-500"}`}
                >
                  {Math.round(apiDetail.confidence_score * 100)}%
                </span>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

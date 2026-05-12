import { useState, useEffect, useRef } from "react";
import {
  Play,
  RefreshCw,
  CheckCircle2,
  Loader2,
  AlertCircle,
  ChevronRight,
  Bot,
  Zap,
  ZapOff,
} from "lucide-react";
import { api, createPipelineStream } from "../../lib/api";
import { useApiData } from "../../hooks/useApiData";
import { PIPELINE_STEPS, getStepByAgentName } from "./pipelineSteps";
import { attachPipelineEventSource } from "../../lib/pipelineSse";
import type { PipelineSSEEvent } from "../../types";

interface LiveAgent {
  name: string;
  order: number;
  status: "waiting" | "processing" | "complete" | "failed";
  decision?: string;
  confidence?: number;
  reasoning?: string;
  evidence?: string[];
  duration_ms?: number;
}

interface ComplaintOption {
  complaint_id: string;
  customer_id: string;
  category?: string;
  pipeline_status?: string;
  severity?: number;
  channel?: string;
}

function ConfBar({ value }: { value: number }) {
  const pct =
    value <= 1 ? Math.round(value * 100) : Math.round(Math.min(value, 100));
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
        <div
          className="h-1.5 rounded-full bg-green-500 transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
    </div>
  );
}

export function PipelineTab() {
  const [selectedId, setSelectedId] = useState<string>("");
  const [liveAgents, setLiveAgents] = useState<LiveAgent[]>([]);
  const [pipelineState, setPipelineState] = useState<
    "idle" | "running" | "done" | "error"
  >("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [finalRoute, setFinalRoute] = useState<string | null>(null);
  const [finalCategory, setFinalCategory] = useState<string | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const esRef = useRef<EventSource | null>(null);
  const detachSseRef = useRef<(() => void) | null>(null);
  const runningRef = useRef(false);

  // Auto Resolution toggle — persisted in localStorage so SubmitTab can read it
  const [autoMode, setAutoMode] = useState(
    () => localStorage.getItem("auto_resolution_enabled") === "true",
  );
  const toggleAutoMode = () => {
    const next = !autoMode;
    setAutoMode(next);
    localStorage.setItem("auto_resolution_enabled", String(next));
  };

  const { data: complaintsData, loading: listLoading } = useApiData(
    () => api.complaints.list({ limit: 100 }),
    [],
  );

  const allComplaints: ComplaintOption[] = complaintsData?.complaints ?? [];
  /** Pipeline tab: only complaints not yet fully analysed */
  const complaints = allComplaints.filter(
    (c) => c.pipeline_status !== "complete",
  );

  // Keep selection in sync: only pending / non-complete complaints appear
  useEffect(() => {
    if (complaints.length === 0) {
      setSelectedId("");
      return;
    }
    const stillValid = complaints.some((c) => c.complaint_id === selectedId);
    if (!selectedId || !stillValid) {
      setSelectedId(complaints[0].complaint_id);
    }
  }, [complaints, selectedId]);

  const selected = complaints.find((c) => c.complaint_id === selectedId);

  const resetPipeline = () => {
    detachSseRef.current?.();
    detachSseRef.current = null;
    esRef.current?.close();
    esRef.current = null;
    runningRef.current = false;
    setLiveAgents([]);
    setPipelineState("idle");
    setErrorMsg(null);
    setFinalRoute(null);
    setFinalCategory(null);
    setLogLines([]);
  };

  const updateAgent = (event: PipelineSSEEvent) => {
    if (!event.agent || event.order == null) return;
    const rawStatus = String(event.status ?? "").toLowerCase();
    setLiveAgents((prev) => {
      const idx = prev.findIndex((a) => a.name === event.agent);
      const agent: LiveAgent = {
        name: event.agent!,
        order: event.order!,
        status:
          rawStatus === "processing"
            ? "processing"
            : rawStatus === "complete"
              ? "complete"
              : rawStatus === "failed"
                ? "failed"
                : "waiting",
        decision: event.decision,
        confidence: event.confidence,
        reasoning: event.reasoning,
        evidence: event.evidence,
        duration_ms: event.duration_ms,
      };
      if (idx >= 0) {
        const updated = [...prev];
        updated[idx] = agent;
        return updated;
      }
      return [...prev, agent].sort((a, b) => a.order - b.order);
    });
  };

  const runPipeline = async () => {
    if (!selectedId) return;
    resetPipeline();
    setPipelineState("running");
    runningRef.current = true;

    try {
      await api.pipeline.run(selectedId);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to start pipeline";
      if (!msg.includes("already")) {
        runningRef.current = false;
        setPipelineState("error");
        setErrorMsg(msg);
        return;
      }
    }

    const es = createPipelineStream(selectedId);
    esRef.current = es;

    detachSseRef.current = attachPipelineEventSource(es, {
      onAgentUpdate: updateAgent,
      onPipelineComplete: (d) => {
        setFinalRoute(typeof d.route === "string" ? d.route : null);
        setFinalCategory(typeof d.category === "string" ? d.category : null);
        runningRef.current = false;
        setPipelineState("done");
        detachSseRef.current?.();
        detachSseRef.current = null;
        es.close();
      },
      onPipelineError: (p) => {
        setErrorMsg(p.error ?? "Pipeline failed");
        runningRef.current = false;
        setPipelineState("error");
        detachSseRef.current?.();
        detachSseRef.current = null;
        es.close();
      },
      onTransportError: () => {
        if (!runningRef.current) return;
        runningRef.current = false;
        setPipelineState("error");
        setErrorMsg(
          'Lost connection to the AI pipeline. Open DevTools (F12) → Network → find "stream". ' +
            "Check: backend on port 8000, frontend proxy, and VITE_API_KEY matches backend API_KEY.",
        );
        detachSseRef.current?.();
        detachSseRef.current = null;
        es.close();
      },
      onLog: (line) => setLogLines((prev) => [...prev.slice(-49), line]),
    });
  };

  // Cleanup on unmount
  useEffect(
    () => () => {
      detachSseRef.current?.();
      esRef.current?.close();
    },
    [],
  );

  const doneCount = liveAgents.filter((a) => a.status === "complete").length;
  const processingAgent = liveAgents.find((a) => a.status === "processing");

  return (
    <div className="flex flex-col lg:flex-row gap-4 md:gap-5">
      {/* ── Left: pipeline step diagram ─────────────────────────────────────── */}
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        {/* Header card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
                <Bot size={18} className="text-ub-blue" />
              </div>
              <div>
                <div className="font-bold text-ub-blue text-sm">
                  Multi-Agent AI Pipeline
                </div>
                <div className="text-xs text-gray-400">
                  10 specialised AI agents work together to analyse and resolve
                  complaints
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {pipelineState !== "idle" && (
                <button
                  onClick={resetPipeline}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50"
                >
                  <RefreshCw size={12} /> Reset
                </button>
              )}

              {/* Auto Resolution toggle */}
              <button
                onClick={toggleAutoMode}
                title={
                  autoMode
                    ? "Auto Resolution is ON — new complaints run through the AI pipeline automatically (no visualization). Click to disable."
                    : "Auto Resolution is OFF — complaints wait in Pending Analysis for manual processing. Click to enable."
                }
                className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border transition-all ${
                  autoMode
                    ? "bg-green-600 text-white border-green-600 hover:bg-green-700 shadow-sm"
                    : "border-gray-200 text-gray-500 bg-white hover:bg-gray-50"
                }`}
              >
                {autoMode ? (
                  <>
                    <Zap size={12} className="fill-white" /> Auto ON
                  </>
                ) : (
                  <>
                    <ZapOff size={12} /> Auto OFF
                  </>
                )}
              </button>

              <button
                onClick={runPipeline}
                disabled={!selectedId || pipelineState === "running"}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white transition-all ${
                  !selectedId || pipelineState === "running"
                    ? "bg-gray-300 cursor-not-allowed"
                    : "bg-ub-red hover:opacity-90 shadow-sm"
                }`}
              >
                {pipelineState === "running" ? (
                  <>
                    <Loader2 size={12} className="animate-spin" /> Processing…
                  </>
                ) : (
                  <>
                    <Play size={12} /> Run AI Analysis
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Progress bar */}
          {pipelineState !== "idle" && (
            <div className="mb-5">
              <div className="flex justify-between text-xs text-gray-400 mb-1.5">
                <span>
                  {pipelineState === "done"
                    ? "Analysis complete"
                    : processingAgent
                      ? `Running: ${processingAgent.name}`
                      : "Starting…"}
                </span>
                <span>
                  {doneCount}/{PIPELINE_STEPS.length} agents done
                </span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full transition-all duration-700 ${
                    pipelineState === "done" ? "bg-green-500" : "bg-ub-blue"
                  }`}
                  style={{
                    width: `${(doneCount / PIPELINE_STEPS.length) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* Step list */}
          <div className="relative">
            <div className="absolute left-5 top-4 bottom-4 w-px bg-gray-100" />
            {PIPELINE_STEPS.map((step) => {
              const liveData = liveAgents.find(
                (a) => a.name === step.agentName,
              );
              const isDone = liveData?.status === "complete";
              const isProcessing = liveData?.status === "processing";
              const isFailed = liveData?.status === "failed";
              const isActive = isDone || isProcessing;

              return (
                <div
                  key={step.id}
                  className="flex items-start gap-4 mb-4 last:mb-0"
                >
                  {/* Node */}
                  <div
                    className="relative z-10 w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-500 border-2"
                    style={{
                      backgroundColor: isActive ? `${step.color}18` : "#F9FAFB",
                      borderColor: isActive ? step.color : "#E5E7EB",
                      boxShadow: isProcessing
                        ? `0 0 16px ${step.color}44`
                        : "none",
                      transform: isProcessing ? "scale(1.1)" : "scale(1)",
                    }}
                  >
                    {isDone && (
                      <CheckCircle2 size={16} style={{ color: step.color }} />
                    )}
                    {isProcessing && (
                      <Loader2
                        size={16}
                        className="animate-spin"
                        style={{ color: step.color }}
                      />
                    )}
                    {isFailed && (
                      <AlertCircle size={16} className="text-red-500" />
                    )}
                    {!liveData && (
                      <div className="w-2 h-2 rounded-full bg-gray-300" />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 pt-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`text-sm font-semibold ${isActive ? "text-gray-800" : "text-gray-400"}`}
                      >
                        {step.label}
                      </span>
                      {step.isParallel && pipelineState !== "idle" && (
                        <span className="text-xs text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded-full font-medium">
                          <Zap size={8} className="inline mr-0.5" />
                          parallel
                        </span>
                      )}
                      {isProcessing && (
                        <span
                          className="text-xs text-white px-2 py-0.5 rounded-full flex-shrink-0"
                          style={{ backgroundColor: step.color }}
                        >
                          Processing…
                        </span>
                      )}
                      {isDone && liveData?.duration_ms && (
                        <span className="text-xs text-green-600 font-medium">
                          {liveData.duration_ms}ms
                        </span>
                      )}
                    </div>
                    <p
                      className={`text-xs mt-0.5 leading-relaxed ${isActive ? "text-gray-500" : "text-gray-300"}`}
                    >
                      {step.description}
                    </p>

                    {/* Live result */}
                    {isDone && liveData?.decision && (
                      <div className="mt-1.5 bg-gray-50 rounded-lg px-2.5 py-1.5 text-xs text-gray-700 border border-gray-100">
                        <span className="text-gray-400">Result: </span>
                        <span className="font-semibold">
                          {liveData.decision}
                        </span>
                        {liveData.confidence !== undefined && (
                          <span className="text-gray-400 ml-2">
                            ({Math.round(liveData.confidence * 100)}% confident)
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Error state */}
          {pipelineState === "error" && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-xl p-3 flex items-start gap-2">
              <AlertCircle
                size={14}
                className="text-red-500 flex-shrink-0 mt-0.5"
              />
              <p className="text-xs text-red-600">{errorMsg}</p>
            </div>
          )}

          {/* Debug log — helps trace SSE / proxy / API key issues */}
          {logLines.length > 0 && (
            <details className="mt-4 rounded-xl border border-gray-200 bg-gray-50 p-3">
              <summary className="text-xs font-semibold text-gray-600 cursor-pointer">
                Connection log (for troubleshooting)
              </summary>
              <pre className="mt-2 text-[10px] leading-relaxed text-gray-700 whitespace-pre-wrap break-all max-h-40 overflow-y-auto font-mono">
                {logLines.join("\n")}
              </pre>
            </details>
          )}
        </div>

        {/* Final result card */}
        {pipelineState === "done" && (
          <div className="bg-white rounded-2xl shadow-sm border border-green-200 p-5">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 size={18} className="text-green-600" />
              <h3 className="text-sm font-bold text-gray-700">
                Analysis Complete
              </h3>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {finalCategory && (
                <div className="bg-blue-50 rounded-xl p-3">
                  <div className="text-xs text-gray-400 mb-0.5">Category</div>
                  <div className="font-semibold text-sm text-gray-800">
                    {finalCategory}
                  </div>
                </div>
              )}
              {finalRoute && (
                <div
                  className={`rounded-xl p-3 ${finalRoute === "auto_respond" ? "bg-green-50" : "bg-amber-50"}`}
                >
                  <div className="text-xs text-gray-400 mb-0.5">Decision</div>
                  <div
                    className={`font-semibold text-sm ${finalRoute === "auto_respond" ? "text-green-700" : "text-amber-700"}`}
                  >
                    {finalRoute === "auto_respond"
                      ? "✅ Response Auto-Sent"
                      : "👤 Needs Human Review"}
                  </div>
                </div>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-3">
              View the full AI analysis in the Complaints tab by selecting this
              complaint.
            </p>
          </div>
        )}

        {/* Routing info cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
            <div className="text-xs font-bold text-green-700 mb-1.5 flex items-center gap-1.5">
              <CheckCircle2 size={12} /> Auto Response
              <span className="font-normal text-gray-400 ml-0.5">
                (AI confidence &gt; 80%)
              </span>
            </div>
            <p className="text-xs text-gray-500 leading-relaxed">
              Draft response is reviewed for accuracy and sent to the customer
              automatically. Full audit log is saved.
            </p>
            <div className="mt-2 text-xs bg-green-50 text-green-700 px-2 py-1 rounded-lg font-medium">
              Avg. response time: 1.2 seconds
            </div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
            <div className="text-xs font-bold text-amber-700 mb-1.5 flex items-center gap-1.5">
              <ChevronRight size={12} /> Human Review
              <span className="font-normal text-gray-400 ml-0.5">
                (AI confidence &lt; 80%)
              </span>
            </div>
            <p className="text-xs text-gray-500 leading-relaxed">
              Complaint and AI draft are sent to a bank officer for review.
              Officer can edit, approve, or escalate.
            </p>
            <div className="mt-2 text-xs bg-amber-50 text-amber-700 px-2 py-1 rounded-lg font-medium">
              Supports continuous AI learning from officer feedback
            </div>
          </div>
        </div>
      </div>

      {/* ── Right: complaint selector + agent details ─────────────────────── */}
      <div className="w-full lg:w-72 lg:flex-shrink-0 flex flex-col gap-4">
        {/* Complaint selector */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
            Pending analysis ({complaints.length})
          </div>
          {listLoading ? (
            <p className="text-xs text-gray-400 py-3 text-center">
              Loading complaints…
            </p>
          ) : complaints.length === 0 ? (
            <p className="text-xs text-gray-500 py-3 text-center leading-relaxed">
              Nothing waiting for analysis. Complaints that are already analysed
              are not listed here—submit a new one or re-open a case from the
              database if you need to re-run.
            </p>
          ) : (
            <div className="space-y-1.5 max-h-72 overflow-y-auto">
              {complaints.map((c) => (
                <button
                  key={c.complaint_id}
                  onClick={() => {
                    setSelectedId(c.complaint_id);
                    resetPipeline();
                  }}
                  className={`w-full text-left px-3 py-2.5 rounded-xl border text-xs transition-all ${
                    selectedId === c.complaint_id
                      ? "border-ub-blue bg-blue-50 text-ub-blue"
                      : "border-gray-100 text-gray-600 hover:border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  <div className="font-mono font-semibold">
                    {c.complaint_id}
                  </div>
                  <div className="text-gray-400 mt-0.5 truncate">
                    {c.customer_id} · {c.channel ?? "Unknown channel"}
                  </div>
                  {c.pipeline_status && c.pipeline_status !== "complete" && (
                    <div className="mt-1 text-xs font-medium text-slate-500">
                      {c.pipeline_status === "pending"
                        ? "Not analysed yet"
                        : c.pipeline_status === "processing" ||
                            c.pipeline_status === "started"
                          ? "Stale — click Run to retry"
                          : "Stopped — click Run to retry"}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Live agent details */}
        {liveAgents.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Agent Results
            </div>
            <div className="space-y-2">
              {liveAgents
                .filter((a) => a.status === "complete" && a.decision)
                .map((a) => {
                  const step = getStepByAgentName(a.name);
                  return (
                    <div
                      key={a.name}
                      className="border border-gray-100 rounded-xl p-3"
                    >
                      <div
                        className="text-xs font-semibold text-gray-700 mb-1.5"
                        style={{ color: step?.color }}
                      >
                        {step?.label ?? a.name}
                      </div>
                      <p className="text-xs text-gray-800 font-medium">
                        {a.decision}
                      </p>
                      {a.confidence !== undefined && (
                        <div className="mt-1.5">
                          <ConfBar value={a.confidence} />
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* Selected complaint info */}
        {selected && pipelineState === "idle" && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              Selected
            </div>
            <div className="font-mono font-bold text-ub-blue text-sm">
              {selected.complaint_id}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {selected.customer_id}
            </div>
            {selected.category && (
              <div className="text-xs text-gray-500 mt-0.5">
                {selected.category}
              </div>
            )}
            <div
              className={`mt-2 text-xs font-medium px-2 py-1 rounded-lg inline-block ${
                selected.pipeline_status === "complete"
                  ? "bg-green-50 text-green-700"
                  : "bg-gray-100 text-gray-500"
              }`}
            >
              {selected.pipeline_status === "complete"
                ? "Already analysed — click Run to re-analyse"
                : 'Click "Run AI Analysis" to begin'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

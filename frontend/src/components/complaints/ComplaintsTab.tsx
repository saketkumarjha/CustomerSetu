import { useState, useCallback } from "react";
import { RefreshCw } from "lucide-react";
import type { Complaint, Status, Severity, TabId } from "../../types";
import { COMPLAINTS } from "../../data/complaints";
import { ComplaintsFilters } from "./ComplaintsFilters";
import { ComplaintsTable } from "./ComplaintsTable";
import { ComplaintDetailModal } from "./ComplaintDetailModal";
import { api, type ApiComplaint } from "../../lib/api";
import { useApiData } from "../../hooks/useApiData";
import {
  severityFromInt,
  statusFromApi,
  slaLabel,
  isSlaBreached,
} from "../../types";

/** Map a backend ApiComplaint to the frontend Complaint shape for the table */
function apiToFrontend(c: ApiComplaint): Complaint {
  const pipelineDone = c.pipeline_status === "complete";

  // Before pipeline completes: severity/sentiment/category are null — use safe defaults
  const sev = pipelineDone ? severityFromInt(c.severity) : "Low";
  const stat = statusFromApi(c.status, c.route);

  // Category: null until classification agent runs
  const category =
    pipelineDone && c.category
      ? c.category
      : pipelineDone
        ? "General"
        : "Analysing…";

  // Sentiment: null until sentiment agent runs
  const sentiment =
    pipelineDone && c.sentiment
      ? (c.sentiment as Complaint["sentiment"])
      : pipelineDone
        ? "Neutral"
        : "Neutral";

  // Compliance type: hide NOT_APPLICABLE and bare dashes
  const rawType = c.compliance_category?.replace(/_/g, " ") ?? "";
  const displayType =
    pipelineDone && rawType && rawType !== "NOT APPLICABLE" && rawType !== "—"
      ? rawType
      : "";

  // Compute SLA — use rbi_tat_deadline > sla_hours > created_at fallback (30-day RBI default)
  const hasSlaData = !!(c.rbi_tat_deadline || c.sla_hours || c.created_at);
  const remaining = hasSlaData
    ? slaLabel(c.sla_hours, c.created_at, c.rbi_tat_deadline)
    : "—";
  const breached = hasSlaData
    ? isSlaBreached(c.sla_hours, c.created_at, c.rbi_tat_deadline)
    : false;

  return {
    id: c.complaint_id,
    customer: c.customer_id,
    accountNo: "",
    phone: "",
    channel: (c.channel as Complaint["channel"]) ?? "Email",
    category,
    type: displayType,
    severity: sev,
    sentiment,
    sentimentScore: 50,
    status: stat,
    slaHours: c.sla_hours ?? 0,
    slaRemaining: remaining,
    slaBreached: breached,
    assignee:
      c.route === "auto_respond"
        ? "Auto-Resolved"
        : c.route === "human_review"
          ? "Pending Review"
          : "—",
    branch: "—",
    date: c.created_at ? c.created_at.slice(0, 10) : "—",
    time: c.created_at
      ? new Date(c.created_at).toLocaleTimeString("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "—",
    description: c.masked_text ?? c.merged_text ?? "—",
    history: [],
    agentResult: {
      classification: {
        category: c.category ?? "—",
        product: c.category ?? "—",
        severity: sev,
        type: c.compliance_category ?? "—",
        confidence: Math.round((c.confidence_score ?? 0) * 100),
      },
      sentiment: {
        emotion: (c.sentiment as Complaint["sentiment"]) ?? "Neutral",
        urgency: Math.round((c.urgency_score ?? 5) * 10),
        score: 50,
        escalate: c.escalation_flag ?? false,
        confidence: Math.round((c.confidence_score ?? 0) * 100),
      },
      duplicate: {
        isDuplicate: c.is_duplicate ?? false,
        similar: 0,
        confidence: 90,
      },
      compliance: {
        flagged: c.is_rbi_reportable ?? false,
        risk: c.is_rbi_reportable
          ? "HIGH"
          : (c.risk_score ?? 0) > 0.5
            ? "MEDIUM"
            : "LOW",
        reason: c.compliance_category ?? "Standard complaint",
        confidence: Math.round((c.confidence_score ?? 0) * 100),
      },
      resolution: c.draft_response ?? "—",
    },
  };
}

export function ComplaintsTab({
  setActive,
}: {
  setActive?: (id: TabId) => void;
}) {
  const [selected, setSelected] = useState<Complaint | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<Status | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [apiComplaintDetail, setApiComplaintDetail] =
    useState<ApiComplaint | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const {
    data: apiData,
    loading: listLoading,
    error: listError,
    refetch,
  } = useApiData(() => api.complaints.list({ limit: 100 }), []);

  const usingApi = !!apiData && !listError;

  const complaints: Complaint[] = usingApi
    ? apiData.complaints.map(apiToFrontend)
    : COMPLAINTS;

  const filtered = complaints.filter((c) => {
    const q = search.toLowerCase();
    const matchesSearch =
      !q ||
      c.customer.toLowerCase().includes(q) ||
      c.id.toLowerCase().includes(q) ||
      c.type.toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q);
    const matchesStatus = statusFilter === "all" || c.status === statusFilter;
    const matchesSeverity =
      severityFilter === "all" || c.severity === severityFilter;
    return matchesSearch && matchesStatus && matchesSeverity;
  });

  const handleSelect = async (c: Complaint) => {
    if (selected?.id === c.id) {
      setSelected(null);
      setApiComplaintDetail(null);
      return;
    }
    setSelected(c);

    // Try to load full detail from API
    if (usingApi) {
      setLoadingDetail(true);
      try {
        const detail = await api.complaints.get(c.id);
        setApiComplaintDetail(detail);
      } catch {
        setApiComplaintDetail(null);
      } finally {
        setLoadingDetail(false);
      }
    }
  };

  const handleClose = () => {
    setSelected(null);
    setApiComplaintDetail(null);
  };

  const refreshComplaintDetail = useCallback(async () => {
    if (!selected || !usingApi) return;
    setLoadingDetail(true);
    try {
      const detail = await api.complaints.get(selected.id);
      setApiComplaintDetail(detail);
    } catch {
      setApiComplaintDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }, [selected, usingApi]);

  const onComplaintUpdated = useCallback(() => {
    refetch();
    void refreshComplaintDetail();
  }, [refetch, refreshComplaintDetail]);

  // Enrich selected complaint with API detail data if available
  const enrichedSelected: Complaint | null =
    selected && apiComplaintDetail
      ? {
          ...selected,
          description:
            apiComplaintDetail.masked_text ??
            apiComplaintDetail.merged_text ??
            selected.description,
          agentResult: {
            ...selected.agentResult,
            resolution:
              apiComplaintDetail.draft_response ??
              selected.agentResult.resolution,
            compliance: {
              ...selected.agentResult.compliance,
              reason:
                apiComplaintDetail.compliance_category?.replace(/_/g, " ") ??
                selected.agentResult.compliance.reason,
            },
          },
        }
      : selected;

  return (
    <div className="flex flex-col gap-4">
      {/* Status bar */}
      <div className="flex items-center gap-3 flex-wrap">
        {listLoading && (
          <span className="text-xs text-gray-400">Loading complaints…</span>
        )}
        {usingApi && !listLoading && (
          <span className="text-xs font-medium text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-md">
            Live · {apiData.total} total
          </span>
        )}
        {listError && (
          <span className="text-xs text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-md">
            Sample data (offline)
          </span>
        )}
        {usingApi && (
          <button
            onClick={refetch}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
          >
            <RefreshCw size={10} /> Refresh
          </button>
        )}
      </div>

      <ComplaintsFilters
        search={search}
        setSearch={setSearch}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        severityFilter={severityFilter}
        setSeverityFilter={setSeverityFilter}
        resultCount={filtered.length}
      />

      {/* Full-width table — modal opens on row click */}
      <div style={{ minHeight: "60vh" }}>
        <ComplaintsTable
          complaints={filtered}
          selected={enrichedSelected}
          onSelect={handleSelect}
        />
      </div>

      {/* Centered modal — works on all screen sizes */}
      {enrichedSelected && (
        <ComplaintDetailModal
          complaint={enrichedSelected}
          onClose={handleClose}
          loadingDetail={loadingDetail}
          apiDetail={apiComplaintDetail}
          pipelineAvailable={usingApi}
          onAfterRunPipeline={() => setActive?.("pipeline")}
          onComplaintUpdated={onComplaintUpdated}
        />
      )}
    </div>
  );
}

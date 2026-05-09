import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import type { Complaint, Status, Severity, TabId } from '../../types'
import { COMPLAINTS } from '../../data/complaints'
import { ComplaintsFilters } from './ComplaintsFilters'
import { ComplaintsTable } from './ComplaintsTable'
import { ComplaintDetailPanel } from './detail/ComplaintDetailPanel'
import { api, type ApiComplaint } from '../../lib/api'
import { useApiData } from '../../hooks/useApiData'
import { severityFromInt, statusFromApi, slaLabel, isSlaBreached } from '../../types'

/** Map a backend ApiComplaint to the frontend Complaint shape for the table */
function apiToFrontend(c: ApiComplaint): Complaint {
  const sev = severityFromInt(c.severity)
  const stat = statusFromApi(c.status, c.route)
  const remaining = slaLabel(c.sla_hours, c.created_at, c.rbi_tat_deadline)
  const breached = isSlaBreached(c.sla_hours, c.created_at, c.rbi_tat_deadline)

  return {
    id: c.complaint_id,
    customer: c.customer_id,
    accountNo: '—',
    phone: '—',
    channel: (c.channel as Complaint['channel']) ?? 'Email',
    category: c.category ?? 'General',
    type: c.compliance_category?.replace(/_/g, ' ') ?? '—',
    severity: sev,
    sentiment: (c.sentiment as Complaint['sentiment']) ?? 'Neutral',
    sentimentScore: 50,
    status: stat,
    slaHours: c.sla_hours ?? 24,
    slaRemaining: remaining,
    slaBreached: breached,
    assignee: c.route === 'auto_respond' ? 'Auto-Resolved' : c.route === 'human_review' ? 'Pending Review' : '—',
    branch: '—',
    date: c.created_at ? c.created_at.slice(0, 10) : '—',
    time: c.created_at ? new Date(c.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—',
    description: c.masked_text ?? c.merged_text ?? '—',
    history: [],
    agentResult: {
      classification: {
        category: c.category ?? '—',
        product: c.category ?? '—',
        severity: sev,
        type: c.compliance_category ?? '—',
        confidence: Math.round((c.confidence_score ?? 0) * 100),
      },
      sentiment: {
        emotion: (c.sentiment as Complaint['sentiment']) ?? 'Neutral',
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
        risk: c.is_rbi_reportable ? 'HIGH' : (c.risk_score ?? 0) > 0.5 ? 'MEDIUM' : 'LOW',
        reason: c.compliance_category ?? 'Standard complaint',
        confidence: Math.round((c.confidence_score ?? 0) * 100),
      },
      resolution: c.draft_response ?? '—',
    },
  }
}

export function ComplaintsTab({ setActive }: { setActive?: (id: TabId) => void }) {
  const [selected, setSelected] = useState<Complaint | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<Status | 'all'>('all')
  const [severityFilter, setSeverityFilter] = useState<Severity | 'all'>('all')
  const [apiComplaintDetail, setApiComplaintDetail] = useState<ApiComplaint | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const { data: apiData, loading: listLoading, error: listError, refetch } = useApiData(
    () => api.complaints.list({ limit: 100 }),
    [],
  )

  const usingApi = !!apiData && !listError

  const complaints: Complaint[] = usingApi
    ? apiData.complaints.map(apiToFrontend)
    : COMPLAINTS

  const filtered = complaints.filter((c) => {
    const q = search.toLowerCase()
    const matchesSearch =
      !q ||
      c.customer.toLowerCase().includes(q) ||
      c.id.toLowerCase().includes(q) ||
      c.type.toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q)
    const matchesStatus = statusFilter === 'all' || c.status === statusFilter
    const matchesSeverity = severityFilter === 'all' || c.severity === severityFilter
    return matchesSearch && matchesStatus && matchesSeverity
  })

  const handleSelect = async (c: Complaint) => {
    if (selected?.id === c.id) {
      setSelected(null)
      setApiComplaintDetail(null)
      return
    }
    setSelected(c)

    // Try to load full detail from API
    if (usingApi) {
      setLoadingDetail(true)
      try {
        const detail = await api.complaints.get(c.id)
        setApiComplaintDetail(detail)
      } catch {
        setApiComplaintDetail(null)
      } finally {
        setLoadingDetail(false)
      }
    }
  }

  const handleClose = () => {
    setSelected(null)
    setApiComplaintDetail(null)
  }

  // Enrich selected complaint with API detail data if available
  const enrichedSelected: Complaint | null = selected && apiComplaintDetail
    ? {
        ...selected,
        description: apiComplaintDetail.masked_text ?? apiComplaintDetail.merged_text ?? selected.description,
        agentResult: {
          ...selected.agentResult,
          resolution: apiComplaintDetail.draft_response ?? selected.agentResult.resolution,
          compliance: {
            ...selected.agentResult.compliance,
            reason: apiComplaintDetail.compliance_category?.replace(/_/g, ' ') ?? selected.agentResult.compliance.reason,
          },
        },
      }
    : selected

  return (
    <div className="flex flex-col gap-4">
      {/* Status bar */}
      <div className="flex items-center gap-3 flex-wrap">
        {listLoading && <span className="text-xs text-gray-400">Loading complaints…</span>}
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
          <button onClick={refetch} className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600">
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

      {/* Desktop: table + side panel */}
      <div className="hidden lg:flex gap-0 overflow-hidden" style={{ minHeight: '60vh' }}>
        <div className="flex-1 min-w-0">
          <ComplaintsTable complaints={filtered} selected={enrichedSelected} onSelect={handleSelect} />
        </div>
        {enrichedSelected && (
          <ComplaintDetailPanel
            complaint={enrichedSelected}
            onClose={handleClose}
            loadingDetail={loadingDetail}
            apiDetail={apiComplaintDetail}
            pipelineAvailable={usingApi}
            onAfterRunPipeline={() => setActive?.('pipeline')}
          />
        )}
      </div>

      {/* Mobile: table full width */}
      <div className="lg:hidden">
        <ComplaintsTable complaints={filtered} selected={enrichedSelected} onSelect={handleSelect} />
      </div>

      {/* Mobile bottom sheet */}
      {enrichedSelected && (
        <div className="lg:hidden fixed inset-0 z-40 flex flex-col justify-end">
          <div className="absolute inset-0 bg-black bg-opacity-40" onClick={handleClose} />
          <div className="relative z-50 rounded-t-2xl overflow-hidden animate-slide-up" style={{ maxHeight: '85vh' }}>
            <ComplaintDetailPanel
              complaint={enrichedSelected}
              onClose={handleClose}
              loadingDetail={loadingDetail}
              apiDetail={apiComplaintDetail}
              pipelineAvailable={usingApi}
              onAfterRunPipeline={() => setActive?.('pipeline')}
            />
          </div>
        </div>
      )}
    </div>
  )
}

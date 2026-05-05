import { useState } from 'react'
import { Shield, AlertTriangle, Clock, CheckCircle2, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../../lib/api'
import { useApiData } from '../../hooks/useApiData'

function CompliancePill({ status }: { status: string }) {
  const map: Record<string, string> = {
    COMPLIANT: 'bg-green-100 text-green-800',
    AT_RISK: 'bg-amber-100 text-amber-800',
    NON_COMPLIANT: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-bold ${map[status] ?? 'bg-gray-100 text-gray-700'}`}>
      {status.replace('_', ' ')}
    </span>
  )
}

function AlertBadge({ level }: { level: string }) {
  if (level === 'BREACHED') return <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-700">BREACHED</span>
  return <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-700">WARNING</span>
}

export function RBITab() {
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null)

  const { data: report, loading: reportLoading, error: reportError, refetch: refetchReport } = useApiData(
    () => api.rbi.report(),
    [],
  )

  const { data: pending, loading: pendingLoading, refetch: refetchPending } = useApiData(
    () => api.rbi.pending(24),
    [],
  )

  const { data: categories } = useApiData(() => api.rbi.categories(), [])

  const allPending = [
    ...(pending?.breached ?? []),
    ...(pending?.approaching_breach ?? []),
  ]

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center">
            <Shield size={20} className="text-ub-red" />
          </div>
          <div>
            <h1 className="text-base font-bold text-gray-800">RBI Compliance Monitor</h1>
            <p className="text-xs text-gray-500">
              Track regulatory compliance and TAT (Turnaround Time) deadlines as per RBI guidelines
            </p>
          </div>
        </div>
        <button
          onClick={() => { refetchReport(); refetchPending() }}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50"
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {reportLoading && (
        <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center text-sm text-gray-400">
          Loading compliance report…
        </div>
      )}

      {reportError && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-5 text-sm text-red-600">
          Could not load compliance data. Make sure the backend is running.
        </div>
      )}

      {report && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              {
                label: 'Total Complaints',
                value: report.summary.total_complaints,
                color: 'text-ub-blue',
                bg: 'bg-blue-50',
              },
              {
                label: 'RBI Reportable',
                value: report.summary.rbi_reportable_complaints,
                color: 'text-red-700',
                bg: 'bg-red-50',
              },
              {
                label: 'TAT Compliance',
                value: `${report.summary.tat_compliance_rate_percent}%`,
                color: report.summary.tat_compliance_rate_percent >= 95 ? 'text-green-700' : 'text-amber-700',
                bg: report.summary.tat_compliance_rate_percent >= 95 ? 'bg-green-50' : 'bg-amber-50',
              },
              {
                label: 'TAT Breached',
                value: report.summary.tat_breached_count,
                color: 'text-red-700',
                bg: 'bg-red-50',
              },
            ].map((card) => (
              <div key={card.label} className={`${card.bg} rounded-xl p-4`}>
                <div className={`text-2xl font-bold mb-1 ${card.color}`}>{card.value}</div>
                <div className="text-xs text-gray-500">{card.label}</div>
              </div>
            ))}
          </div>

          {/* Compliance status + notes */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <h2 className="text-sm font-bold text-gray-700">Overall Compliance Status</h2>
              <CompliancePill status={report.compliance_status} />
            </div>
            {report.compliance_notes.length > 0 && (
              <div className="space-y-2">
                {report.compliance_notes.map((note, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-gray-700 bg-gray-50 rounded-lg p-3">
                    <span>{note}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Category breakdown */}
          {report.rbi_category_breakdown.length > 0 && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <h2 className="text-sm font-bold text-gray-700 mb-3">Breakdown by RBI Category</h2>
              <div className="space-y-2">
                {report.rbi_category_breakdown.map((cat) => (
                  <div key={cat.rbi_category} className="border border-gray-100 rounded-xl overflow-hidden">
                    <button
                      onClick={() => setExpandedCategory(expandedCategory === cat.rbi_category ? null : cat.rbi_category)}
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="font-medium text-sm text-gray-800 truncate">{cat.display_label}</div>
                        {cat.tat_breached_count > 0 && (
                          <span className="px-1.5 py-0.5 rounded text-xs bg-red-100 text-red-700 font-semibold flex-shrink-0">
                            {cat.tat_breached_count} breached
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0">
                        <span className="text-xs text-gray-400">{cat.total_count} cases</span>
                        {expandedCategory === cat.rbi_category ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </div>
                    </button>
                    {expandedCategory === cat.rbi_category && (
                      <div className="px-4 pb-3 grid grid-cols-2 sm:grid-cols-4 gap-3 bg-gray-50 border-t border-gray-100">
                        {[
                          { label: 'Total', value: cat.total_count, color: 'text-gray-800' },
                          { label: 'Human Review', value: cat.human_review_count, color: 'text-amber-700' },
                          { label: 'Resolved', value: cat.resolved_count, color: 'text-green-700' },
                          { label: 'TAT Breached', value: cat.tat_breached_count, color: cat.tat_breached_count > 0 ? 'text-red-700' : 'text-green-700' },
                        ].map((stat) => (
                          <div key={stat.label} className="pt-3 text-center">
                            <div className={`text-lg font-bold ${stat.color}`}>{stat.value}</div>
                            <div className="text-xs text-gray-400">{stat.label}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Pending / At-risk complaints */}
      {!pendingLoading && pending && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock size={16} className="text-amber-600" />
            <h2 className="text-sm font-bold text-gray-700">
              Complaints Approaching Deadline
            </h2>
            {allPending.length > 0 && (
              <span className="ml-auto text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-semibold">
                {allPending.length} require action
              </span>
            )}
          </div>

          {allPending.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 rounded-xl p-4">
              <CheckCircle2 size={16} />
              All RBI complaints are within their TAT deadline. No action needed.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[500px]">
                <thead>
                  <tr className="text-xs text-gray-400 font-semibold uppercase tracking-wide border-b border-gray-100">
                    <th className="text-left pb-2 pr-4">Complaint ID</th>
                    <th className="text-left pb-2 pr-4">Category</th>
                    <th className="text-left pb-2 pr-4">RBI Category</th>
                    <th className="text-left pb-2 pr-4">Deadline</th>
                    <th className="text-left pb-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {allPending.map((item) => (
                    <tr key={item.complaint_id} className="border-b border-gray-50 last:border-0">
                      <td className="py-2.5 pr-4 font-mono text-xs font-semibold text-ub-blue">
                        {item.complaint_id}
                      </td>
                      <td className="py-2.5 pr-4 text-xs text-gray-700">{item.category ?? '—'}</td>
                      <td className="py-2.5 pr-4 text-xs text-gray-500">
                        {item.compliance_category?.replace(/_/g, ' ')}
                      </td>
                      <td className="py-2.5 pr-4 text-xs text-gray-500">
                        {item.hours_remaining < 0
                          ? `${Math.abs(Math.round(item.hours_remaining))}h overdue`
                          : `${Math.round(item.hours_remaining)}h left`}
                      </td>
                      <td className="py-2.5">
                        <AlertBadge level={item.alert_level} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* RBI Category Reference */}
      {categories && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle size={16} className="text-ub-blue" />
            <h2 className="text-sm font-bold text-gray-700">RBI Category Reference Guide</h2>
            <span className="ml-auto text-xs text-gray-400">{categories.total_categories} categories</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[600px]">
              <thead>
                <tr className="text-gray-400 font-semibold uppercase tracking-wide border-b border-gray-100">
                  <th className="text-left pb-2 pr-3">Category</th>
                  <th className="text-left pb-2 pr-3">SLA</th>
                  <th className="text-left pb-2 pr-3">Penalty / Day</th>
                  <th className="text-left pb-2 pr-3">Mandatory Human</th>
                  <th className="text-left pb-2">RBI Reportable</th>
                </tr>
              </thead>
              <tbody>
                {categories.categories.map((cat) => (
                  <tr key={cat.category_code} className="border-b border-gray-50 last:border-0">
                    <td className="py-2.5 pr-3 font-medium text-gray-800">{cat.display_label}</td>
                    <td className="py-2.5 pr-3 text-gray-600">{cat.sla_label}</td>
                    <td className="py-2.5 pr-3 text-gray-600">
                      {cat.penalty_per_day > 0 ? `₹${cat.penalty_per_day.toLocaleString()}` : '—'}
                    </td>
                    <td className="py-2.5 pr-3">
                      {cat.supervisor_override_always_human ? (
                        <span className="text-amber-700 font-semibold">Yes</span>
                      ) : (
                        <span className="text-gray-400">No</span>
                      )}
                    </td>
                    <td className="py-2.5">
                      {cat.is_rbi_reportable ? (
                        <span className="text-red-700 font-semibold">Yes</span>
                      ) : (
                        <span className="text-gray-400">No</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

import { Search } from 'lucide-react'
import type { Status, Severity } from '../../types'

interface Props {
  search: string
  setSearch: (v: string) => void
  statusFilter: Status | 'all'
  setStatusFilter: (v: Status | 'all') => void
  severityFilter: Severity | 'all'
  setSeverityFilter: (v: Severity | 'all') => void
  resultCount: number
}

const STATUS_OPTIONS: Array<Status | 'all'> = ['all', 'Open', 'In Progress', 'Pending', 'Resolved', 'Escalated']
const SEVERITY_OPTIONS: Array<Severity | 'all'> = ['all', 'Critical', 'High', 'Medium', 'Low']

const selectCls =
  'border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-ub-blue text-gray-700 bg-white'

export function ComplaintsFilters({
  search,
  setSearch,
  statusFilter,
  setStatusFilter,
  severityFilter,
  setSeverityFilter,
  resultCount,
}: Props) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-3 flex flex-col sm:flex-row flex-wrap gap-2 items-stretch sm:items-center">
      {/* Search */}
      <div className="relative w-full sm:flex-1" style={{ minWidth: '160px' }}>
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search customer, ID or type…"
          className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-ub-blue"
        />
      </div>

      <div className="flex gap-2 flex-wrap">
        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as Status | 'all')}
          className={selectCls}
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s === 'all' ? 'All Status' : s}
            </option>
          ))}
        </select>

        {/* Severity filter */}
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value as Severity | 'all')}
          className={selectCls}
        >
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s === 'all' ? 'All Severity' : s}
            </option>
          ))}
        </select>

        <span className="text-xs text-gray-400 font-medium self-center whitespace-nowrap px-1">
          {resultCount} results
        </span>
      </div>
    </div>
  )
}

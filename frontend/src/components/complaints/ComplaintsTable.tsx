import type { Complaint } from '../../types'
import { SeverityBadge } from '../ui/SeverityBadge'
import { StatusBadge } from '../ui/StatusBadge'
import { ChannelBadge } from '../ui/ChannelBadge'
import { SentimentBadge } from '../ui/SentimentBadge'
import { SlaBadge } from '../ui/SlaBadge'

interface Props {
  complaints: Complaint[]
  selected: Complaint | null
  onSelect: (c: Complaint) => void
}

const HEADERS = [
  'ID', 'Customer', 'Channel', 'Category / Type',
  'Severity', 'Sentiment', 'Status', 'SLA',
]

export function ComplaintsTable({ complaints, selected, onSelect }: Props) {
  return (
    <div className="glass-panel overflow-hidden flex-1 flex flex-col min-h-0">
      <div className="overflow-auto flex-1">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 border-b border-gray-100">
            <tr>
              {HEADERS.map((h) => (
                <th
                  key={h}
                  className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {complaints.map((c) => {
              const isSelected = selected?.id === c.id
              return (
                <tr
                  key={c.id}
                  onClick={() => onSelect(c)}
                  className={`border-b border-gray-50 cursor-pointer transition-colors last:border-0 ${
                    isSelected
                      ? 'bg-ub-blue-light'
                      : 'hover:bg-slate-50'
                  }`}
                >
                  <td className="px-4 py-3 text-xs font-mono font-semibold text-ub-blue whitespace-nowrap">
                    {c.id}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-gray-800 whitespace-nowrap text-sm">{c.customer}</div>
                    <div className="text-xs text-gray-400">{c.accountNo}</div>
                  </td>
                  <td className="px-4 py-3">
                    <ChannelBadge channel={c.channel} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm text-gray-800 whitespace-nowrap">{c.category}</div>
                    <div className="text-xs text-gray-400">{c.type}</div>
                  </td>
                  <td className="px-4 py-3">
                    <SeverityBadge severity={c.severity} />
                  </td>
                  <td className="px-4 py-3">
                    <SentimentBadge sentiment={c.sentiment} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <SlaBadge breached={c.slaBreached} label={c.slaRemaining} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {complaints.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <div className="text-sm">No complaints match the current filters.</div>
          </div>
        )}
      </div>
    </div>
  )
}

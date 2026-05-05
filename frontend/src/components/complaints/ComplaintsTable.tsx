import { Mail, Phone, Globe, Smartphone, MessageSquare } from 'lucide-react'
import type { Complaint, Channel } from '../../types'
import { SeverityBadge } from '../ui/SeverityBadge'
import { StatusBadge } from '../ui/StatusBadge'
import { getSentimentColor } from '../../utils/styles'

interface Props {
  complaints: Complaint[]
  selected: Complaint | null
  onSelect: (c: Complaint) => void
}

function ChannelIcon({ channel }: { channel: Channel }) {
  const cls = 'w-3.5 h-3.5 text-gray-400'
  switch (channel) {
    case 'Email': return <Mail className={cls} />
    case 'Phone': return <Phone className={cls} />
    case 'Web Form': return <Globe className={cls} />
    case 'Mobile App': return <Smartphone className={cls} />
    case 'Social Media': return <MessageSquare className={cls} />
  }
}

const HEADERS = [
  'ID', 'Customer', 'Channel', 'Category / Type',
  'Severity', 'Sentiment', 'Status', 'SLA', 'Assigned To',
]

export function ComplaintsTable({ complaints, selected, onSelect }: Props) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex-1 flex flex-col min-h-0">
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
                    <div className="flex items-center gap-1.5 text-xs text-gray-600 whitespace-nowrap">
                      <ChannelIcon channel={c.channel} />
                      {c.channel}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm text-gray-800 whitespace-nowrap">{c.category}</div>
                    <div className="text-xs text-gray-400">{c.type}</div>
                  </td>
                  <td className="px-4 py-3">
                    <SeverityBadge severity={c.severity} />
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-semibold" style={{ color: getSentimentColor(c.sentiment) }}>
                      {c.sentiment}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3 text-xs font-medium whitespace-nowrap">
                    <span className={c.slaBreached ? 'text-red-600 font-semibold' : 'text-gray-600'}>
                      {c.slaBreached ? 'BREACHED' : c.slaRemaining}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">{c.assignee}</td>
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

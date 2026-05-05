import { Mail, Phone, Globe, Smartphone, MessageSquare, ArrowRight } from 'lucide-react'
import type { Complaint, Channel, TabId } from '../../types'
import { SeverityBadge } from '../ui/SeverityBadge'
import { StatusBadge } from '../ui/StatusBadge'

interface Props {
  complaints: Complaint[]
  setActive: (id: TabId) => void
}

function ChannelIcon({ channel }: { channel: Channel }) {
  const cls = 'w-4 h-4 text-gray-400'
  switch (channel) {
    case 'Email': return <Mail className={cls} />
    case 'Phone': return <Phone className={cls} />
    case 'Web Form': return <Globe className={cls} />
    case 'Mobile App': return <Smartphone className={cls} />
    case 'Social Media': return <MessageSquare className={cls} />
  }
}

export function RecentComplaintsFeed({ complaints, setActive }: Props) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 flex-shrink-0">
        <div className="font-semibold text-sm text-ub-blue">Recent Complaints</div>
        <button
          onClick={() => setActive('complaints')}
          className="flex items-center gap-1 text-xs font-semibold text-ub-red hover:underline"
        >
          View All <ArrowRight size={12} />
        </button>
      </div>

      <div className="overflow-auto flex-1">
        {complaints.map((c) => (
          <div
            key={c.id}
            className="flex items-center gap-3 px-5 py-3 border-b border-gray-50 hover:bg-slate-50 transition-colors last:border-0"
          >
            <ChannelIcon channel={c.channel} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs font-mono text-gray-400">{c.id}</span>
                <SeverityBadge severity={c.severity} />
              </div>
              <div className="text-sm font-medium text-gray-800 truncate">
                {c.customer} — {c.type}
              </div>
            </div>
            <div className="text-right flex-shrink-0 space-y-1">
              <StatusBadge status={c.status} />
              <div
                className={`text-xs block ${c.slaBreached ? 'text-red-600 font-semibold' : 'text-gray-400'}`}
              >
                {c.slaBreached ? 'SLA Breached' : c.slaRemaining}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

import { Mail, Phone, Globe, Smartphone, MessageSquare } from 'lucide-react'
import type { Channel } from '../../types'

interface ChannelStat {
  channel: Channel
  count: number
  color: string
  total: number
}

interface Props {
  stats: ChannelStat[]
}

function ChannelIcon({ channel }: { channel: Channel }) {
  const cls = 'w-4 h-4 flex-shrink-0'
  switch (channel) {
    case 'Email': return <Mail className={cls} />
    case 'Phone': return <Phone className={cls} />
    case 'Web Form': return <Globe className={cls} />
    case 'Mobile App': return <Smartphone className={cls} />
    case 'Social Media': return <MessageSquare className={cls} />
  }
}

export function ChannelBar({ stats }: Props) {
  return (
    <div className="glass-panel p-5 h-full">
      <div className="font-semibold text-sm text-ub-blue mb-4">Complaints by Channel</div>
      <div className="space-y-3">
        {stats.map((s) => (
          <div key={s.channel} className="flex items-center gap-3">
            <div className="text-gray-400">
              <ChannelIcon channel={s.channel} />
            </div>
            <div className="flex-1">
              <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-slate-700">{s.channel}</span>
                <span className="font-semibold tabular-nums text-ub-blue">
                  {s.count}
                </span>
              </div>
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200/60">
                <div
                  className="h-1.5 rounded-full bg-ub-blue/85 transition-all duration-500"
                  style={{ width: `${(s.count / s.total) * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

import {
  Mail,
  Phone,
  Globe,
  Smartphone,
  MessageSquare,
  HelpCircle,
} from "lucide-react";
import type { Channel } from "../../types";

interface ChannelStat {
  channel: Channel | string;
  count: number;
  color: string;
  total: number;
}

interface Props {
  stats: ChannelStat[];
}

function ChannelIcon({ channel }: { channel: string }) {
  const cls = "w-3.5 h-3.5 flex-shrink-0";
  switch (channel) {
    case "Email":
      return <Mail className={cls} />;
    case "Phone":
      return <Phone className={cls} />;
    case "Web Form":
      return <Globe className={cls} />;
    case "Mobile App":
      return <Smartphone className={cls} />;
    case "Social Media":
      return <MessageSquare className={cls} />;
    default:
      return <HelpCircle className={cls} />;
  }
}

export function ChannelBar({ stats }: Props) {
  const maxCount = Math.max(...stats.map((s) => s.count), 1);

  return (
    <div className="glass-panel p-4 h-full">
      <div className="flex items-center gap-2 mb-4">
        <div className="text-xs font-semibold text-slate-800">By Channel</div>
        <span className="ml-auto text-[10px] text-slate-400 tabular-nums">
          {stats.reduce((a, s) => a + s.count, 0)} total
        </span>
      </div>
      <div className="space-y-2.5">
        {stats.map((s) => (
          <div key={s.channel} className="flex items-center gap-2.5">
            <div className="text-slate-400 flex-shrink-0">
              <ChannelIcon channel={s.channel} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-slate-700 truncate">
                  {s.channel}
                </span>
                <span className="font-semibold tabular-nums text-ub-blue ml-2 flex-shrink-0">
                  {s.count}
                </span>
              </div>
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-1.5 rounded-full bg-ub-blue/80 transition-all duration-700"
                  style={{ width: `${(s.count / maxCount) * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
        {stats.length === 0 && (
          <p className="text-xs text-slate-400 text-center py-4">
            No channel data
          </p>
        )}
      </div>
    </div>
  );
}

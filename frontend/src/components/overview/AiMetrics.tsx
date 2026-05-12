import { Bot, Zap, Clock } from "lucide-react";

interface Props {
  autoRate?: number;
  rbiCount?: number;
  confidence?: number;
  duplicateCount?: number;
  autoSentCount?: number;
  totalComplaints?: number;
}

export function AiMetrics({
  autoRate,
  rbiCount,
  confidence,
  duplicateCount,
  autoSentCount,
  totalComplaints,
}: Props) {
  const isLive = autoRate !== undefined;

  const metrics = isLive
    ? [
        {
          label: "Auto-resolution rate",
          value: `${autoRate!.toFixed(1)}%`,
          bar: autoRate! / 100,
          color: "bg-emerald-500",
        },
        {
          label: "Avg model confidence",
          value:
            confidence !== undefined
              ? `${(confidence * 100).toFixed(1)}%`
              : "—",
          bar: confidence ?? 0,
          color:
            confidence && confidence >= 0.8
              ? "bg-emerald-500"
              : confidence && confidence >= 0.6
                ? "bg-amber-400"
                : "bg-red-400",
        },
        {
          label: "Auto-sent to customer",
          value: autoSentCount ?? "—",
          bar: totalComplaints ? (autoSentCount ?? 0) / totalComplaints : 0,
          color: "bg-ub-blue",
        },
        {
          label: "Duplicates detected",
          value: duplicateCount ?? "—",
          bar: totalComplaints ? (duplicateCount ?? 0) / totalComplaints : 0,
          color: "bg-amber-400",
        },
        {
          label: "RBI-flagged cases",
          value: rbiCount ?? "—",
          bar: totalComplaints ? (rbiCount ?? 0) / totalComplaints : 0,
          color: "bg-red-400",
        },
      ]
    : [
        {
          label: "Classification accuracy",
          value: "98.2%",
          bar: 0.982,
          color: "bg-emerald-500",
        },
        {
          label: "Draft responses produced",
          value: "95.7%",
          bar: 0.957,
          color: "bg-ub-blue",
        },
        {
          label: "Duplicates detected today",
          value: "3",
          bar: 0.15,
          color: "bg-amber-400",
        },
        {
          label: "Compliance reviews open",
          value: "4",
          bar: 0.2,
          color: "bg-red-400",
        },
        {
          label: "Average model confidence",
          value: "94.1%",
          bar: 0.941,
          color: "bg-emerald-500",
        },
      ];

  return (
    <div className="glass-panel p-4">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-7 h-7 rounded-lg bg-ub-blue/10 flex items-center justify-center">
          <Bot size={13} className="text-ub-blue" />
        </div>
        <div className="text-xs font-semibold text-slate-800">
          AI Pipeline Summary
        </div>
        {isLive ? (
          <span className="ml-auto flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Live
          </span>
        ) : (
          <span className="ml-auto text-[10px] font-medium text-slate-400 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-full">
            Demo
          </span>
        )}
      </div>

      <div className="space-y-3">
        {metrics.map((m) => (
          <div key={m.label}>
            <div className="flex justify-between items-center text-xs mb-1">
              <span className="text-slate-500">{m.label}</span>
              <span className="font-semibold text-slate-800 tabular-nums">
                {String(m.value)}
              </span>
            </div>
            <div className="h-1 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${m.color}`}
                style={{ width: `${Math.min(m.bar * 100, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {isLive && (
        <div className="mt-4 pt-3 border-t border-slate-100 grid grid-cols-2 gap-2">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Zap size={11} className="text-ub-blue" />
            <span>~5s pipeline</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Clock size={11} className="text-slate-400" />
            <span>10 agents</span>
          </div>
        </div>
      )}
    </div>
  );
}

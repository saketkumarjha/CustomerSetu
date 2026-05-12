interface Props {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  sub: string;
  valueColor?: string;
  trend?: string;
  trendUp?: boolean;
}

export function KpiCard({
  icon,
  label,
  value,
  sub,
  valueColor = "#003087",
  trend,
  trendUp,
}: Props) {
  return (
    <div className="glass-panel p-4 md:p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="w-9 h-9 rounded-xl bg-slate-100/90 flex items-center justify-center text-slate-500 flex-shrink-0 border border-slate-200/60">
          {icon}
        </div>
        {trend && (
          <span
            className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${
              trendUp === true
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : trendUp === false
                  ? "bg-red-50 text-red-600 border-red-200"
                  : "bg-slate-100 text-slate-600 border-slate-200"
            }`}
          >
            {trend}
          </span>
        )}
      </div>
      <div>
        <div
          className="text-2xl md:text-3xl font-bold tabular-nums leading-none mb-1"
          style={{ color: valueColor }}
        >
          {value}
        </div>
        <div className="text-xs font-semibold text-slate-700 leading-snug">
          {label}
        </div>
        <div className="text-xs text-slate-400 mt-0.5">{sub}</div>
      </div>
    </div>
  );
}

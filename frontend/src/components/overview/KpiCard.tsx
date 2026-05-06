interface Props {
  icon: React.ReactNode
  label: string
  value: number | string
  sub: string
  valueColor: string
  trend: string
}

export function KpiCard({ icon, label, value, sub, valueColor, trend }: Props) {
  return (
    <div className="glass-panel p-4 md:p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="w-8 h-8 md:w-9 md:h-9 rounded-md bg-slate-100/90 flex items-center justify-center text-slate-500 flex-shrink-0 border border-slate-200/60">
          {icon}
        </div>
        <span className="text-xs font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200/80">
          {trend}
        </span>
      </div>
      <div className="text-2xl md:text-3xl font-bold mb-1 tabular-nums" style={{ color: valueColor }}>
        {value}
      </div>
      <div className="text-xs md:text-sm font-semibold text-slate-800 leading-snug">{label}</div>
      <div className="text-xs text-slate-500 mt-0.5">{sub}</div>
    </div>
  )
}

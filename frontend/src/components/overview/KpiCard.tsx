interface Props {
  icon: React.ReactNode
  label: string
  value: number | string
  sub: string
  valueColor: string
  trend: string
  trendUp: boolean
}

export function KpiCard({ icon, label, value, sub, valueColor, trend, trendUp }: Props) {
  return (
    <div className="bg-white rounded-xl p-4 md:p-5 shadow-sm border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <div className="w-8 h-8 md:w-9 md:h-9 rounded-lg bg-slate-50 flex items-center justify-center text-gray-500 flex-shrink-0">
          {icon}
        </div>
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            trendUp ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'
          }`}
        >
          {trend}
        </span>
      </div>
      <div className="text-2xl md:text-3xl font-bold mb-1" style={{ color: valueColor }}>
        {value}
      </div>
      <div className="text-xs md:text-sm font-semibold text-gray-700 leading-snug">{label}</div>
      <div className="text-xs text-gray-400 mt-0.5">{sub}</div>
    </div>
  )
}

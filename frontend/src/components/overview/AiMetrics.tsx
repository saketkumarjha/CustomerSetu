import { Bot } from 'lucide-react'

interface Props {
  autoRate?: number
  rbiCount?: number
  confidence?: number
}

const DEFAULT_METRICS = [
  { label: 'Classification accuracy', value: '98.2%' },
  { label: 'Draft responses produced', value: '95.7%' },
  { label: 'Duplicates detected today', value: '3' },
  { label: 'Compliance reviews open', value: '4' },
  { label: 'Average model confidence', value: '94.1%' },
]

export function AiMetrics({ autoRate, rbiCount, confidence }: Props) {
  const metrics =
    autoRate !== undefined
      ? [
          { label: 'Auto-resolution rate', value: `${autoRate.toFixed(1)}%` },
          { label: 'RBI-flagged cases', value: `${rbiCount ?? 0}` },
          {
            label: 'Average confidence',
            value: confidence !== undefined ? `${(confidence * 100).toFixed(1)}%` : '—',
          },
          { label: 'Analysis steps per case', value: '10' },
          { label: 'Typical processing time', value: '~5 s' },
        ]
      : DEFAULT_METRICS

  return (
    <div className="glass-panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <Bot size={14} className="text-ub-blue" />
        <div className="text-xs font-semibold text-slate-800">Model summary</div>
        {autoRate !== undefined && (
          <span className="ml-auto text-[10px] uppercase tracking-wide text-slate-500 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-md font-medium">
            Live
          </span>
        )}
      </div>
      <div className="space-y-2">
        {metrics.map((m) => (
          <div key={m.label} className="flex justify-between items-center text-xs gap-3">
            <span className="text-slate-500">{m.label}</span>
            <span className="font-semibold text-slate-800 tabular-nums">{m.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

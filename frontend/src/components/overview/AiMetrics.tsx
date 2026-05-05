import { Bot } from 'lucide-react'

interface Props {
  autoRate?: number
  rbiCount?: number
  confidence?: number
}

const DEFAULT_METRICS = [
  { label: 'Auto-classification accuracy', value: '98.2%', color: '#16A34A' },
  { label: 'Draft responses generated', value: '95.7%', color: '#003087' },
  { label: 'Duplicate complaints caught', value: '3 today', color: '#7C3AED' },
  { label: 'Compliance flags raised', value: '4 active', color: '#C8102E' },
  { label: 'Avg agent confidence', value: '94.1%', color: '#D97706' },
]

export function AiMetrics({ autoRate, rbiCount, confidence }: Props) {
  const metrics = autoRate !== undefined
    ? [
        { label: 'Auto-resolution rate', value: `${autoRate.toFixed(1)}%`, color: '#16A34A' },
        { label: 'RBI flagged cases', value: `${rbiCount ?? 0}`, color: '#C8102E' },
        { label: 'Avg agent confidence', value: confidence !== undefined ? `${(confidence * 100).toFixed(1)}%` : '—', color: '#D97706' },
        { label: 'AI agents per complaint', value: '10 agents', color: '#003087' },
        { label: 'Avg pipeline time', value: '~5 seconds', color: '#7C3AED' },
      ]
    : DEFAULT_METRICS

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Bot size={14} className="text-ub-blue" />
        <div className="text-xs font-bold text-ub-blue">AI Performance</div>
        {autoRate !== undefined && (
          <span className="ml-auto text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">Live</span>
        )}
      </div>
      <div className="space-y-2">
        {metrics.map((m) => (
          <div key={m.label} className="flex justify-between items-center text-xs">
            <span className="text-gray-500">{m.label}</span>
            <span className="font-bold" style={{ color: m.color }}>{m.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

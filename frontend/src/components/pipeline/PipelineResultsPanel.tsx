import type { Complaint } from '../../types'
import { getSentimentColor } from '../../utils/styles'

interface Props {
  complaint: Complaint
}

export function PipelineResultsPanel({ complaint }: Props) {
  const r = complaint.agentResult
  const avgConfidence = Math.round(
    (r.classification.confidence +
      r.sentiment.confidence +
      r.duplicate.confidence +
      r.compliance.confidence) /
      4,
  )

  const rows: Array<{ label: string; value: string; color: string }> = [
    { label: 'Category', value: r.classification.category, color: '#003087' },
    { label: 'Product', value: r.classification.product, color: '#374151' },
    {
      label: 'Severity',
      value: r.classification.severity,
      color:
        r.classification.severity === 'Critical'
          ? '#DC2626'
          : r.classification.severity === 'High'
          ? '#B45309'
          : '#1D4ED8',
    },
    {
      label: 'Emotion',
      value: complaint.sentiment,
      color: getSentimentColor(complaint.sentiment),
    },
    { label: 'Urgency', value: `${r.sentiment.urgency}%`, color: '#D97706' },
    {
      label: 'Duplicate',
      value: r.duplicate.isDuplicate ? 'Yes' : 'No',
      color: r.duplicate.isDuplicate ? '#D97706' : '#16A34A',
    },
    {
      label: 'Compliance Risk',
      value: r.compliance.risk,
      color:
        r.compliance.risk === 'HIGH'
          ? '#DC2626'
          : r.compliance.risk === 'MEDIUM'
          ? '#D97706'
          : '#16A34A',
    },
    {
      label: 'Action',
      value: r.sentiment.escalate ? 'Human Review' : 'Automated',
      color: r.sentiment.escalate ? '#D97706' : '#16A34A',
    },
  ]

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Selected Complaint</div>
        <div className="font-mono font-bold text-ub-blue text-sm">{complaint.id}</div>
        <div className="text-xs text-gray-500 mt-0.5">{complaint.customer} — {complaint.type}</div>
      </div>

      {/* Results */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex-1">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Agent Results</div>
        <div className="space-y-0">
          {rows.map((row) => (
            <div key={row.label} className="flex justify-between text-xs py-2 border-b border-gray-50 last:border-0">
              <span className="text-gray-400">{row.label}</span>
              <span className="font-semibold" style={{ color: row.color }}>
                {row.value}
              </span>
            </div>
          ))}
        </div>

        <div className="mt-3 rounded-lg p-2.5 bg-purple-50 border border-purple-100">
          <div className="text-xs text-purple-600">
            Avg classification confidence:{' '}
            <span className="font-bold text-purple-800">{avgConfidence}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}

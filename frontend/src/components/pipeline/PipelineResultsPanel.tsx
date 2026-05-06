import type { Complaint } from '../../types'

interface Props {
  complaint: Complaint
}

const valCls = 'font-medium text-slate-800 text-right max-w-[55%]'

export function PipelineResultsPanel({ complaint }: Props) {
  const r = complaint.agentResult
  const avgConfidence = Math.round(
    (r.classification.confidence +
      r.sentiment.confidence +
      r.duplicate.confidence +
      r.compliance.confidence) /
      4,
  )

  const rows: Array<{ label: string; value: string }> = [
    { label: 'Category', value: r.classification.category },
    { label: 'Product', value: r.classification.product },
    { label: 'Severity', value: r.classification.severity },
    { label: 'Emotion', value: complaint.sentiment },
    { label: 'Urgency', value: `${r.sentiment.urgency}%` },
    { label: 'Possible duplicate', value: r.duplicate.isDuplicate ? 'Yes' : 'No' },
    { label: 'Risk level', value: r.compliance.risk },
    { label: 'Next step', value: r.sentiment.escalate ? 'Officer review' : 'Automated path' },
  ]

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="glass-panel p-4">
        <div className="text-xs font-medium text-slate-500 mb-1">Selected</div>
        <div className="font-mono font-semibold text-ub-blue text-sm">{complaint.id}</div>
        <div className="text-xs text-slate-500 mt-0.5">
          {complaint.customer} — {complaint.type}
        </div>
      </div>

      <div className="glass-panel p-4 flex-1">
        <div className="text-xs font-medium text-slate-500 mb-3">Analysis output</div>
        <div className="space-y-0">
          {rows.map((row) => (
            <div
              key={row.label}
              className="flex justify-between gap-3 text-xs py-2 border-b border-slate-100 last:border-0"
            >
              <span className="text-slate-500 shrink-0">{row.label}</span>
              <span className={valCls}>{row.value}</span>
            </div>
          ))}
        </div>

        <div className="mt-3 rounded-md p-2.5 bg-ub-blue-light/60 border border-slate-200/80 text-xs text-slate-700">
          Average step confidence:{' '}
          <span className="font-semibold text-ub-blue">{avgConfidence}%</span>
        </div>
      </div>
    </div>
  )
}

import type { Complaint } from '../../types'
import { COMPLAINTS } from '../../data/complaints'

interface Props {
  selected: Complaint
  onSelect: (c: Complaint) => void
}

export function ComplaintSelector({ selected, onSelect }: Props) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
      <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Select Complaint</div>
      <div className="space-y-1.5 max-h-64 overflow-y-auto">
        {COMPLAINTS.slice(0, 8).map((c) => (
          <button
            key={c.id}
            onClick={() => onSelect(c)}
            className={`w-full text-left px-3 py-2.5 rounded-lg border text-xs transition-all ${
              selected.id === c.id
                ? 'border-ub-blue bg-ub-blue-light text-ub-blue'
                : 'border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-slate-50'
            }`}
          >
            <div className="font-mono font-semibold">{c.id}</div>
            <div className="truncate text-gray-400 mt-0.5">
              {c.customer} — {c.type}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

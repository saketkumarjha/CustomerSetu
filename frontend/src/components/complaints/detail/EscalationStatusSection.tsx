import { useEffect, useState } from 'react'
import { Loader2, Layers, AlertTriangle } from 'lucide-react'
import { api, type EscalationStatusResponse } from '../../../lib/api'

interface Props {
  complaintId: string | undefined
  enabled: boolean
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  } catch {
    return iso
  }
}

export function EscalationStatusSection({ complaintId, enabled }: Props) {
  const [data, setData] = useState<EscalationStatusResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled || !complaintId) {
      setData(null)
      setError(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    api.complaints
      .escalationStatus(complaintId)
      .then((r) => {
        if (!cancelled) setData(r)
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setError(e.message)
          setData(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [complaintId, enabled])

  if (!enabled || !complaintId) return null

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 flex items-center gap-1.5">
        <Layers size={12} className="text-slate-500" />
        Auto-escalation status
      </div>
      <p className="text-xs text-slate-600 leading-relaxed mb-3">
        Read-only view of how the routing engine moved this complaint across support tiers (branch → zonal → …).
        This does not trigger escalation; it reflects what already ran in the pipeline.
      </p>

      {loading && (
        <div className="flex items-center gap-2 text-xs text-slate-500 py-2">
          <Loader2 size={12} className="animate-spin" /> Loading escalation snapshot…
        </div>
      )}

      {error && (
        <p className="text-xs text-ub-red bg-ub-red/5 border border-ub-red/20 rounded-md px-2 py-1.5">{error}</p>
      )}

      {!loading && !error && data && (
        <div className="space-y-3 text-xs">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-md bg-slate-50 border border-slate-100 px-2 py-1.5">
              <div className="text-slate-400 text-[10px] uppercase tracking-wide">Current tier</div>
              <div className="font-semibold text-slate-800">
                {data.current_tier != null ? `Tier ${data.current_tier}` : '—'}
              </div>
            </div>
            <div className="rounded-md bg-slate-50 border border-slate-100 px-2 py-1.5">
              <div className="text-slate-400 text-[10px] uppercase tracking-wide">Tier hops</div>
              <div className="font-semibold text-slate-800">{data.escalation_count}</div>
            </div>
          </div>

          {data.escalation_path && data.escalation_path.length > 0 && (
            <div>
              <div className="text-slate-400 text-[10px] uppercase mb-1">Path</div>
              <div className="flex flex-wrap gap-1">
                {data.escalation_path.map((t, i) => (
                  <span
                    key={`${t}-${i}`}
                    className="bg-ub-blue/10 text-ub-blue border border-ub-blue/20 px-2 py-0.5 rounded-md font-mono text-[11px]"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {data.is_escalating && (
              <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 text-amber-900 border border-amber-200/80 px-2 py-0.5 text-[11px] font-medium">
                Escalation in progress
              </span>
            )}
            {data.escalation_loop_detected && (
              <span className="inline-flex items-center gap-1 rounded-md bg-ub-red/10 text-ub-red border border-ub-red/25 px-2 py-0.5 text-[11px] font-medium">
                <AlertTriangle size={10} /> Loop detected
              </span>
            )}
          </div>

          <div className="text-slate-600">
            <span className="text-slate-400">Next action: </span>
            <span className="font-medium text-slate-800">{data.next_action}</span>
          </div>
          <div className="text-slate-500">
            Last escalation: <span className="text-slate-700">{formatWhen(data.last_escalation_at)}</span>
          </div>

          {data.escalation_history && data.escalation_history.length > 0 && (
            <div>
              <div className="text-slate-400 text-[10px] uppercase mb-2">Audit trail</div>
              <ul className="space-y-2 max-h-40 overflow-y-auto border border-slate-100 rounded-md p-2 bg-slate-50/80">
                {data.escalation_history.map((row, idx) => (
                  <li key={idx} className="border-b border-slate-100 last:border-0 pb-2 last:pb-0">
                    <div className="flex justify-between gap-2 text-[11px]">
                      <span className="font-medium text-slate-800">
                        {row.from_tier != null && row.to_tier != null
                          ? `Tier ${row.from_tier} → ${row.to_tier}`
                          : 'Escalation event'}
                      </span>
                      <span className="text-slate-400 shrink-0">{formatWhen(row.escalated_at)}</span>
                    </div>
                    {row.escalation_reason && (
                      <div className="text-slate-600 mt-0.5">{row.escalation_reason}</div>
                    )}
                    {row.escalation_decision_reasoning && (
                      <div className="text-slate-500 mt-0.5 leading-relaxed">{row.escalation_decision_reasoning}</div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {data.escalation_count === 0 &&
            (!data.escalation_history || data.escalation_history.length === 0) &&
            !data.is_escalating && (
              <p className="text-slate-500 italic">No automatic tier hops recorded for this complaint yet.</p>
            )}
        </div>
      )}
    </section>
  )
}

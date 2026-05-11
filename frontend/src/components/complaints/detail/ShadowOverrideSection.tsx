import { useEffect, useState, type FormEvent } from 'react'
import { Loader2, Send, Clock, ShieldAlert } from 'lucide-react'
import type { ApiComplaint } from '../../../lib/api'
import { api } from '../../../lib/api'

interface Props {
  apiDetail: ApiComplaint
  onApplied: () => void
}

function useDeadlineCountdown(iso: string | null | undefined): 'expired' | string | null {
  const [label, setLabel] = useState<string | null>(null)

  useEffect(() => {
    if (!iso) {
      setLabel(null)
      return
    }
    const parse = () => {
      const end = new Date(iso.includes('Z') || iso.includes('+') ? iso : iso.replace(' ', 'T') + 'Z')
      const ms = end.getTime() - Date.now()
      if (ms <= 0) return 'expired' as const
      const m = Math.floor(ms / 60000)
      const s = Math.floor((ms % 60000) / 1000)
      return `${m}m ${s}s left`
    }
    const first = parse()
    if (first === 'expired') {
      setLabel('expired')
      return
    }
    setLabel(first)
    const id = window.setInterval(() => {
      const v = parse()
      setLabel(v === 'expired' ? 'expired' : v)
    }, 1000)
    return () => window.clearInterval(id)
  }, [iso])

  if (label === 'expired') return 'expired'
  return label
}

export function ShadowOverrideSection({ apiDetail, onApplied }: Props) {
  const status = apiDetail.status
  const overridden = apiDetail.shadow_overridden === true
  const closed = status === 'override_closed'

  const showSuccessOnly = overridden || closed
  const showActiveShadow = status === 'shadow_sent' && !overridden

  const countdown = useDeadlineCountdown(apiDetail.shadow_override_deadline ?? undefined)

  const [agentId, setAgentId] = useState('desk_agent')
  const [corrected, setCorrected] = useState('')
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (showActiveShadow && apiDetail.draft_response) {
      setCorrected(apiDetail.draft_response)
    }
  }, [showActiveShadow, apiDetail.complaint_id, apiDetail.draft_response])

  if (!showSuccessOnly && !showActiveShadow) return null

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!corrected.trim() || !reason.trim()) {
      setError('Corrected message and reason are required.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await api.complaints.shadowOverride(apiDetail.complaint_id, {
        agent_id: agentId.trim() || 'desk_agent',
        corrected_response: corrected.trim(),
        override_reason: reason.trim(),
      })
      onApplied()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Override failed')
    } finally {
      setLoading(false)
    }
  }

  if (showSuccessOnly) {
    return (
      <section className="rounded-xl border border-emerald-200 bg-emerald-50/90 p-4">
        <div className="text-xs font-semibold text-emerald-900 uppercase tracking-wide mb-1 flex items-center gap-1.5">
          <ShieldAlert size={12} /> Shadow correction complete
        </div>
        <p className="text-xs text-emerald-800 leading-relaxed">
          A corrected reply was sent to the customer after the initial shadow auto-send. This case is no longer in the
          override window.
        </p>
      </section>
    )
  }

  const windowOpen = countdown !== 'expired'

  return (
    <section className="rounded-xl border border-amber-300/80 bg-gradient-to-b from-amber-50 to-white p-4 shadow-sm">
      <div className="text-xs font-semibold text-amber-950 uppercase tracking-wide mb-1 flex items-center gap-1.5">
        <ShieldAlert size={12} className="text-amber-700" />
        Shadow auto-reply — correction window
      </div>
      <p className="text-xs text-amber-950/85 leading-relaxed mb-3">
        The system already sent an AI draft to the customer (shadow mode). If that message was wrong or incomplete, send a
        <strong> corrected </strong>
        reply here within the time limit. This replaces what went out for this complaint only.
      </p>

      <div className="rounded-md bg-white/80 border border-amber-200/90 p-3 mb-3 text-xs">
        <div className="text-slate-500 text-[10px] uppercase mb-1">Message sent to customer (reference)</div>
        <p className="text-slate-800 leading-relaxed whitespace-pre-wrap">
          {apiDetail.draft_response ?? '—'}
        </p>
      </div>

      <div className="flex items-center gap-2 text-xs mb-3">
        <Clock size={12} className="text-amber-800" />
        {apiDetail.shadow_override_deadline ? (
          windowOpen ? (
            <span className="font-semibold text-amber-900">
              Override closes in: {countdown ?? '…'}
            </span>
          ) : (
            <span className="font-semibold text-ub-red">Override window has expired.</span>
          )
        ) : (
          <span className="text-slate-600">No deadline on record — contact support if you need to correct this send.</span>
        )}
      </div>

      {!windowOpen && (
        <p className="text-xs text-ub-red bg-ub-red/5 border border-ub-red/20 rounded-md px-2 py-1.5 mb-0">
          Corrections are only accepted within one hour of shadow send. Further changes must follow your normal process.
        </p>
      )}

      {windowOpen && (
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-1">Your agent ID</label>
            <input
              type="text"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              className="w-full text-xs border border-slate-200 rounded-md px-2 py-1.5 focus:outline-none focus:border-ub-blue"
              placeholder="e.g. desk_agent"
            />
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-1">Corrected reply to customer</label>
            <textarea
              value={corrected}
              onChange={(e) => setCorrected(e.target.value)}
              rows={5}
              className="w-full text-xs text-slate-800 border border-slate-200 rounded-md p-2 resize-none focus:outline-none focus:border-ub-blue leading-relaxed"
              required
            />
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-1">Reason for correction</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              className="w-full text-xs border border-slate-200 rounded-md p-2 resize-none focus:outline-none focus:border-ub-blue"
              placeholder="e.g. Incorrect loan outstanding quoted"
              required
            />
          </div>

          {error && (
            <p className="text-xs text-ub-red bg-ub-red/5 border border-ub-red/20 rounded-md px-2 py-1.5">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !corrected.trim() || !reason.trim()}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-md text-xs font-semibold text-white bg-amber-800 hover:bg-amber-900 disabled:opacity-50 transition-colors"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Send corrected reply to customer
          </button>
        </form>
      )}
    </section>
  )
}

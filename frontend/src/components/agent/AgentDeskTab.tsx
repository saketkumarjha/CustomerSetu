import { useCallback, useState } from 'react'
import {
  UserCircle2,
  RefreshCw,
  Loader2,
  Inbox,
  Users,
  ChevronRight,
  Sparkles,
} from 'lucide-react'
import { api, type AgentComplaintContext, type AgentQueueItem } from '../../lib/api'
import { useApiData } from '../../hooks/useApiData'

const STORAGE_AGENT = 'ub_agent_desk_id'
const STORAGE_TIER = 'ub_agent_desk_tier'

function loadStoredAgent(): string {
  try {
    return localStorage.getItem(STORAGE_AGENT) ?? 'desk_agent'
  } catch {
    return 'desk_agent'
  }
}

function loadStoredTier(): number {
  try {
    const t = parseInt(localStorage.getItem(STORAGE_TIER) ?? '1', 10)
    return Number.isFinite(t) && t >= 1 && t <= 5 ? t : 1
  } catch {
    return 1
  }
}

/** Turn backend labels into everyday words */
function urgencyWords(priority?: string): string {
  switch (priority) {
    case 'CRITICAL':
      return 'Very urgent'
    case 'HIGH':
      return 'Urgent'
    case 'MEDIUM':
      return 'Normal'
    case 'LOW':
      return 'Can wait'
    default:
      return priority ?? '—'
  }
}

function queueStatusWords(status?: string): string {
  switch (status) {
    case 'QUEUED':
      return 'Waiting in line'
    case 'ASSIGNED':
      return 'Assigned'
    case 'IN_REVIEW':
      return 'Someone is reviewing'
    default:
      return status ?? '—'
  }
}

function percentOrDash(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${Math.round(v * 100)}%`
}

export function AgentDeskTab() {
  const [draftName, setDraftName] = useState(loadStoredAgent)
  const [draftLevel, setDraftLevel] = useState(loadStoredTier)
  const [staffId, setStaffId] = useState(loadStoredAgent)
  const [supportLevel, setSupportLevel] = useState(loadStoredTier)

  const applyIdentity = useCallback(() => {
    const name = draftName.trim() || 'desk_agent'
    const lvl = Math.min(5, Math.max(1, Math.floor(draftLevel)))
    try {
      localStorage.setItem(STORAGE_AGENT, name)
      localStorage.setItem(STORAGE_TIER, String(lvl))
    } catch {
      /* ignore */
    }
    setStaffId(name)
    setSupportLevel(lvl)
  }, [draftName, draftLevel])

  const { data: myNumbers, loading: metricsLoading, error: metricsError, refetch: refetchMetrics } =
    useApiData(() => api.agent.metrics(staffId), [staffId])

  const {
    data: teamSnapshot,
    loading: teamLoading,
    error: teamError,
    refetch: refetchTeam,
  } = useApiData(() => api.agent.teamMetrics(supportLevel), [supportLevel])

  const {
    data: waitingList,
    loading: queueLoading,
    error: queueError,
    refetch: refetchQueue,
  } = useApiData(() => api.agent.queue({ agentId: staffId, tierLevel: supportLevel }), [staffId, supportLevel])

  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null)
  const [caseDetails, setCaseDetails] = useState<AgentComplaintContext | null>(null)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [detailsError, setDetailsError] = useState<string | null>(null)

  const [nextLoading, setNextLoading] = useState(false)
  const [nextMessage, setNextMessage] = useState<string | null>(null)

  const refreshAll = () => {
    refetchMetrics()
    refetchTeam()
    refetchQueue()
    setNextMessage(null)
  }

  const openCase = async (row: AgentQueueItem) => {
    setSelectedCaseId(row.id)
    setDetailsLoading(true)
    setDetailsError(null)
    try {
      const ctx = await api.agent.complaintContext(row.id, staffId)
      setCaseDetails(ctx)
    } catch (e) {
      setCaseDetails(null)
      setDetailsError(e instanceof Error ? e.message : 'Could not load this case')
    } finally {
      setDetailsLoading(false)
    }
  }

  const pickNextCase = async () => {
    setNextLoading(true)
    setNextMessage(null)
    setDetailsError(null)
    try {
      const res = await api.agent.nextComplaint({ agent_id: staffId, tier_level: supportLevel })
      setNextMessage(res.message)
      if (res.complaint) {
        setSelectedCaseId(res.complaint.complaint_id ?? null)
        setCaseDetails(res.complaint)
      } else {
        setSelectedCaseId(null)
        setCaseDetails(null)
      }
      refetchQueue()
    } catch (e) {
      setNextMessage(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setNextLoading(false)
    }
  }

  const summaryText =
    caseDetails?.complaint_summary && typeof caseDetails.complaint_summary === 'object'
      ? (caseDetails.complaint_summary as { masked_text?: string }).masked_text
      : undefined
  const draftText =
    caseDetails?.draft_response && typeof caseDetails.draft_response === 'object'
      ? (caseDetails.draft_response as { text?: string }).text
      : undefined

  return (
    <div className="space-y-4">
      {/* Intro */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
        <div className="flex items-start gap-3 flex-wrap">
          <div className="w-10 h-10 rounded-xl bg-sky-50 flex items-center justify-center flex-shrink-0">
            <UserCircle2 size={22} className="text-sky-700" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-base font-bold text-gray-800">Agent desk</h1>
            <p className="text-xs text-gray-600 leading-relaxed mt-1">
              This is your workspace: see how you are doing, what is waiting in line, and open the next customer case.
              Words here are kept simple on purpose.
            </p>
          </div>
          <button
            type="button"
            onClick={refreshAll}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50"
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* Who you are */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm space-y-3">
        <h2 className="text-sm font-bold text-gray-800">Who is using this screen?</h2>
        <p className="text-xs text-gray-500">
          Enter the same staff login your bank uses for this tool, and pick your support level (1 = front line, higher
          numbers = more senior). We save this on this device so you do not have to type it every time.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 items-end">
          <label className="text-xs flex-1 w-full">
            <span className="text-gray-500 block mb-1">Staff ID</span>
            <input
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. desk_agent"
            />
          </label>
          <label className="text-xs w-full sm:w-36">
            <span className="text-gray-500 block mb-1">Support level (1–5)</span>
            <input
              type="number"
              min={1}
              max={5}
              value={draftLevel}
              onChange={(e) => setDraftLevel(parseInt(e.target.value, 10) || 1)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <button
            type="button"
            onClick={applyIdentity}
            className="w-full sm:w-auto px-4 py-2 rounded-lg bg-sky-700 text-white text-xs font-semibold hover:bg-sky-800"
          >
            Save
          </button>
        </div>
      </div>

      {/* Your numbers */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        <h2 className="text-sm font-bold text-gray-800 mb-1">Your numbers</h2>
        <p className="text-xs text-gray-500 mb-4">Based on cases you have already finished (when the system has data).</p>
        {metricsLoading && (
          <div className="flex items-center gap-2 text-xs text-gray-400 py-6">
            <Loader2 size={14} className="animate-spin" /> Loading…
          </div>
        )}
        {metricsError && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            Could not load your numbers. Is the server running? ({metricsError})
          </p>
        )}
        {myNumbers && !metricsLoading && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">Cases you closed</div>
              <div className="text-2xl font-bold text-gray-900">{myNumbers.total_reviewed}</div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">Typical time per case</div>
              <div className="text-xl font-bold text-gray-900">{myNumbers.avg_review_time}</div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">Open cases assigned to you</div>
              <div className="text-2xl font-bold text-sky-700">{myNumbers.current_workload}</div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">You approved the draft as-is</div>
              <div className="text-xl font-bold text-emerald-700">{percentOrDash(myNumbers.acceptance_rate)}</div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">You changed the draft before sending</div>
              <div className="text-xl font-bold text-amber-800">{percentOrDash(myNumbers.edit_rate)}</div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">You turned down the draft</div>
              <div className="text-xl font-bold text-red-700">{percentOrDash(myNumbers.rejection_rate)}</div>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-4">
              <div className="text-gray-500 mb-1">You sent the case to a higher level</div>
              <div className="text-xl font-bold text-violet-800">{percentOrDash(myNumbers.escalation_rate)}</div>
            </div>
          </div>
        )}
      </div>

      {/* Team */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Users size={16} className="text-gray-500" />
          <h2 className="text-sm font-bold text-gray-800">Your team at this support level</h2>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          Everyone working at support level <strong>{supportLevel}</strong>, and how many cases are still waiting in the
          shared line.
        </p>
        {teamLoading && (
          <div className="flex items-center gap-2 text-xs text-gray-400 py-4">
            <Loader2 size={14} className="animate-spin" /> Loading…
          </div>
        )}
        {teamError && (
          <p className="text-xs text-amber-800 bg-amber-50 border rounded-lg px-3 py-2">{teamError}</p>
        )}
        {teamSnapshot && !teamLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="rounded-lg bg-slate-50 border border-slate-100 p-3">
                <div className="text-gray-500">People on this level</div>
                <div className="text-lg font-bold text-gray-900">{teamSnapshot.agent_count}</div>
              </div>
              <div className="rounded-lg bg-slate-50 border border-slate-100 p-3">
                <div className="text-gray-500">Cases closed by the team</div>
                <div className="text-lg font-bold text-gray-900">{teamSnapshot.total_reviewed}</div>
              </div>
              <div className="rounded-lg bg-slate-50 border border-slate-100 p-3 sm:col-span-2">
                <div className="text-gray-500">Cases waiting in the shared line</div>
                <div className="text-lg font-bold text-sky-700">{teamSnapshot.queue_size}</div>
              </div>
            </div>
            {teamSnapshot.agents.length > 0 && (
              <div className="border border-gray-100 rounded-xl overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500 text-left">
                      <th className="py-2 px-3">Staff ID</th>
                      <th className="py-2 px-3 text-right">Cases closed</th>
                      <th className="py-2 px-3 text-right">Open now</th>
                    </tr>
                  </thead>
                  <tbody>
                    {teamSnapshot.agents.map((a) => (
                      <tr key={a.agent_id} className="border-t border-gray-50">
                        <td className="py-2 px-3 font-mono">{a.agent_id}</td>
                        <td className="py-2 px-3 text-right">{a.total_reviewed}</td>
                        <td className="py-2 px-3 text-right">{a.current_workload}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Waiting list */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
          <div className="flex items-center gap-2">
            <Inbox size={16} className="text-gray-500" />
            <div>
              <h2 className="text-sm font-bold text-gray-800">Cases waiting</h2>
              <p className="text-xs text-gray-500">
                Same support level as above. “Assigned to you” counts cases that list your staff ID.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void pickNextCase()}
            disabled={nextLoading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-sky-700 text-white text-xs font-semibold hover:bg-sky-800 disabled:opacity-50"
          >
            {nextLoading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            Give me the next case in line
          </button>
        </div>

        {nextMessage && (
          <p className="text-xs text-gray-700 bg-sky-50 border border-sky-100 rounded-lg px-3 py-2">{nextMessage}</p>
        )}

        {queueLoading && (
          <div className="flex items-center gap-2 text-xs text-gray-400 py-6">
            <Loader2 size={14} className="animate-spin" /> Loading the waiting list…
          </div>
        )}
        {queueError && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            {queueError}. If you never set up the queue in the database, this list may stay empty.
          </p>
        )}
        {waitingList && !queueLoading && (
          <>
            <div className="flex flex-wrap gap-3 text-xs">
              <span className="bg-gray-100 px-2 py-1 rounded-md">
                In line: <strong>{waitingList.total_queue_size}</strong>
              </span>
              <span className="bg-gray-100 px-2 py-1 rounded-md">
                Linked to you: <strong>{waitingList.my_assigned}</strong>
              </span>
              <span className="bg-gray-100 px-2 py-1 rounded-md">
                You are reviewing: <strong>{waitingList.my_in_review}</strong>
              </span>
            </div>
            {waitingList.complaints.length === 0 ? (
              <p className="text-sm text-gray-500 py-6 text-center">No cases are waiting right now. Good moment for a break.</p>
            ) : (
              <div className="overflow-x-auto border border-gray-100 rounded-xl">
                <table className="w-full text-xs min-w-[720px]">
                  <thead>
                    <tr className="text-gray-500 bg-gray-50 text-left">
                      <th className="py-2 px-3">Case reference</th>
                      <th className="py-2 px-3">Topic</th>
                      <th className="py-2 px-3">How urgent</th>
                      <th className="py-2 px-3">Line status</th>
                      <th className="py-2 px-3 text-right">About how long</th>
                      <th className="py-2 px-3 text-right">Hours left on clock</th>
                      <th className="py-2 px-3 w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {waitingList.complaints.map((row) => (
                      <tr key={row.id} className="border-t border-gray-50 hover:bg-gray-50/80">
                        <td className="py-2 px-3 font-mono font-semibold text-sky-700">{row.id}</td>
                        <td className="py-2 px-3">{row.category ?? '—'}</td>
                        <td className="py-2 px-3">{urgencyWords(row.priority)}</td>
                        <td className="py-2 px-3">{queueStatusWords(row.queue_status)}</td>
                        <td className="py-2 px-3 text-right">{row.estimated_review_time ?? '—'}</td>
                        <td className="py-2 px-3 text-right">
                          {row.sla_remaining_hours != null
                            ? row.sla_remaining_hours < 0
                              ? `${Math.abs(row.sla_remaining_hours)}h overdue`
                              : `${row.sla_remaining_hours}h`
                            : '—'}
                        </td>
                        <td className="py-2 px-3">
                          <button
                            type="button"
                            onClick={() => void openCase(row)}
                            className="text-sky-700 font-semibold hover:underline inline-flex items-center gap-0.5"
                          >
                            Open <ChevronRight size={12} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {/* Selected case — plain language */}
      {(selectedCaseId || detailsLoading) && (
        <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm space-y-3">
          <h2 className="text-sm font-bold text-gray-800">Case you opened</h2>
          {detailsLoading && (
            <div className="flex items-center gap-2 text-xs text-gray-400 py-4">
              <Loader2 size={14} className="animate-spin" /> Loading case details…
            </div>
          )}
          {detailsError && <p className="text-xs text-ub-red">{detailsError}</p>}
          {!detailsLoading && caseDetails && (
            <>
              <p className="text-xs text-gray-500">
                Reference: <span className="font-mono font-semibold text-gray-800">{selectedCaseId}</span>
              </p>
              <div className="rounded-xl bg-gray-50 border border-gray-100 p-4 space-y-3">
                <div>
                  <div className="text-xs font-semibold text-gray-600 mb-1">What the customer said</div>
                  <p className="text-xs text-gray-800 leading-relaxed whitespace-pre-wrap">
                    {summaryText ?? '—'}
                  </p>
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-600 mb-1">Suggested reply from the assistant</div>
                  <p className="text-xs text-gray-800 leading-relaxed whitespace-pre-wrap">
                    {draftText ?? '—'}
                  </p>
                </div>
              </div>
              {caseDetails.suggested_actions && Array.isArray(caseDetails.suggested_actions) && (
                <div className="text-xs">
                  <div className="font-semibold text-gray-700 mb-2">Typical next steps (ideas, not buttons)</div>
                  <ul className="list-disc pl-5 space-y-1 text-gray-600">
                    {(caseDetails.suggested_actions as string[]).map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="text-xs text-gray-400">
                To approve, edit, or send this case up the line using the bank’s official actions, use the tools your
                administrator linked to this system—or the All Complaints screen when those buttons are connected.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  )
}

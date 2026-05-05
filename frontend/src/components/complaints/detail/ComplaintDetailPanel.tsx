import { useState, useEffect } from 'react'
import {
  X, User, MessageCircle, Copy, Shield, Send,
  RotateCcw, ArrowUpCircle, Loader2, Bot, Clock, CheckCircle2,
} from 'lucide-react'
import type { Complaint } from '../../../types'
import type { ApiComplaint, AgentDecision } from '../../../lib/api'
import { SeverityBadge } from '../../ui/SeverityBadge'
import { getSentimentColor, getInitials, getActorColor } from '../../../utils/styles'
import { api } from '../../../lib/api'

interface Props {
  complaint: Complaint
  onClose: () => void
  loadingDetail?: boolean
  apiDetail?: ApiComplaint | null
}

export function ComplaintDetailPanel({ complaint, onClose, loadingDetail, apiDetail }: Props) {
  const [draft, setDraft] = useState(complaint.agentResult.resolution)
  const [sent, setSent] = useState(false)
  const [submittingFeedback, setSubmittingFeedback] = useState(false)
  const [feedbackDone, setFeedbackDone] = useState<'accepted' | 'rejected' | null>(null)
  const [agentDecisions, setAgentDecisions] = useState<AgentDecision[]>([])
  const [loadingExplanation, setLoadingExplanation] = useState(false)

  useEffect(() => {
    setDraft(complaint.agentResult.resolution !== '—' ? complaint.agentResult.resolution : '')
    setSent(false)
    setFeedbackDone(null)
    setAgentDecisions([])
  }, [complaint.id, complaint.agentResult.resolution])

  // Load explanation trace when an API complaint is selected and has been through pipeline
  useEffect(() => {
    if (!apiDetail || apiDetail.pipeline_status !== 'complete') return
    setLoadingExplanation(true)
    api.complaints.explanation(apiDetail.complaint_id)
      .then((r) => setAgentDecisions(r.explanation_trace))
      .catch(() => {})
      .finally(() => setLoadingExplanation(false))
  }, [apiDetail?.complaint_id, apiDetail?.pipeline_status])

  const r = complaint.agentResult

  const handleApprove = async () => {
    if (!apiDetail) { setSent(true); return }
    setSubmittingFeedback(true)
    try {
      await api.feedback.submitAgent({
        complaint_id: apiDetail.complaint_id,
        agent_id: 'RM',
        action: draft === apiDetail.draft_response ? 'accept' : 'edit',
        original_draft: apiDetail.draft_response ?? '',
        final_response: draft,
      })
      setFeedbackDone('accepted')
      setSent(true)
    } catch {
      setSent(true)
    } finally {
      setSubmittingFeedback(false)
    }
  }

  const handleReject = async () => {
    if (!apiDetail) return
    setSubmittingFeedback(true)
    try {
      await api.feedback.submitAgent({
        complaint_id: apiDetail.complaint_id,
        agent_id: 'RM',
        action: 'reject',
        original_draft: apiDetail.draft_response ?? '',
        rejection_reason: 'Officer rejected draft — needs manual response',
      })
      setFeedbackDone('rejected')
    } catch { /* ignore */ }
    finally { setSubmittingFeedback(false) }
  }

  return (
    <div className="w-full lg:w-[460px] lg:min-w-[460px] flex flex-col bg-white lg:border-l border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 bg-ub-blue flex-shrink-0">
        <div>
          <div className="text-white font-bold text-sm font-mono">{complaint.id}</div>
          <div className="text-blue-300 text-xs">360° Complaint View</div>
        </div>
        <div className="flex items-center gap-2">
          {loadingDetail && <Loader2 size={14} className="text-blue-200 animate-spin" />}
          {apiDetail?.pipeline_status === 'complete' && (
            <span className="text-xs bg-green-500 bg-opacity-30 text-green-200 px-2 py-0.5 rounded-full">
              AI Analysed
            </span>
          )}
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-full bg-white bg-opacity-20 text-white flex items-center justify-center hover:bg-opacity-30 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="overflow-y-auto flex-1 p-4 space-y-4">

        {/* Customer info */}
        <section className="rounded-xl p-3 border border-blue-100 bg-blue-50">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
            <User size={11} /> Customer Details
          </div>
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-full bg-ub-blue text-white flex items-center justify-center font-bold text-xs flex-shrink-0">
              {getInitials(complaint.customer)}
            </div>
            <div>
              <div className="font-semibold text-sm text-gray-800">{complaint.customer}</div>
              {complaint.accountNo !== '—' && (
                <div className="text-xs text-gray-500">{complaint.accountNo} · {complaint.branch}</div>
              )}
              {complaint.phone !== '—' && <div className="text-xs text-gray-400">{complaint.phone}</div>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 mt-3 text-xs">
            <div><span className="text-gray-400">Channel: </span><span className="font-medium">{complaint.channel}</span></div>
            <div><span className="text-gray-400">Date: </span><span className="font-medium">{complaint.date}</span></div>
            <div className="flex items-center gap-1.5">
              <span className="text-gray-400">Severity: </span>
              <SeverityBadge severity={complaint.severity} />
            </div>
            <div>
              <span className="text-gray-400">SLA: </span>
              <span className={`font-semibold ${complaint.slaBreached ? 'text-red-600' : 'text-green-600'}`}>
                {complaint.slaBreached ? 'BREACHED' : complaint.slaRemaining}
              </span>
            </div>
          </div>
        </section>

        {/* Complaint text */}
        <section>
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Complaint Description</div>
          <p className="text-xs text-gray-700 leading-relaxed bg-gray-50 rounded-xl p-3 border border-gray-100">
            {complaint.description}
          </p>
          {apiDetail?.language && apiDetail.language !== 'en' && (
            <p className="text-xs text-purple-600 mt-1 bg-purple-50 px-2 py-1 rounded-lg">
              Language detected: <strong>{apiDetail.language.toUpperCase()}</strong> (auto-translated)
            </p>
          )}
        </section>

        {/* AI analysis — use explanation_trace if available, else use agentResult */}
        <section>
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Bot size={11} /> AI Analysis Results
            {loadingExplanation && <Loader2 size={10} className="animate-spin text-gray-400" />}
          </div>

          {/* Live explanation trace from backend */}
          {agentDecisions.length > 0 ? (
            <div className="space-y-2">
              {agentDecisions.map((d) => (
                <div key={d.agent_name} className={`rounded-xl p-3 border text-xs ${
                  d.status === 'complete' ? 'border-green-100 bg-green-50'
                  : d.status === 'failed' ? 'border-red-100 bg-red-50'
                  : 'border-gray-100 bg-gray-50'
                }`}>
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="font-bold text-gray-700 flex items-center gap-1">
                      <CheckCircle2 size={10} className="text-green-600" />
                      {d.agent_name}
                    </span>
                    <div className="flex items-center gap-2">
                      {d.confidence !== undefined && (
                        <span className="text-gray-400">{Math.round(d.confidence * 100)}% conf.</span>
                      )}
                      {d.duration_ms && (
                        <span className="text-gray-400 flex items-center gap-0.5">
                          <Clock size={9} /> {d.duration_ms}ms
                        </span>
                      )}
                    </div>
                  </div>
                  {d.decision && (
                    <p className="text-gray-800 font-medium">{d.decision}</p>
                  )}
                  {d.reasoning && (
                    <p className="text-gray-500 mt-1 leading-relaxed">{d.reasoning}</p>
                  )}
                  {d.evidence && d.evidence.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {d.evidence.map((ev) => (
                        <span key={ev} className="bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded text-xs">
                          {ev}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            /* Fallback: render from agentResult */
            <div className="space-y-2">
              {/* Classification */}
              <div className="rounded-xl p-3 border border-blue-100 bg-blue-50">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-bold text-ub-blue">Classification</span>
                  <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                    {r.classification.confidence}% conf.
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <div><span className="text-gray-400">Category: </span><span className="font-medium">{r.classification.category}</span></div>
                  <div><span className="text-gray-400">Product: </span><span className="font-medium">{r.classification.product}</span></div>
                  <div className="col-span-2"><span className="text-gray-400">Type: </span><span className="font-medium">{r.classification.type}</span></div>
                </div>
              </div>

              {/* Sentiment */}
              <div className="rounded-xl p-3 border border-purple-100 bg-purple-50">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-bold text-purple-800 flex items-center gap-1">
                    <MessageCircle size={11} /> Sentiment
                  </span>
                  <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">
                    {r.sentiment.confidence}% conf.
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1 text-xs">
                  <div>
                    <span className="text-gray-400">Emotion: </span>
                    <span className="font-semibold" style={{ color: getSentimentColor(r.sentiment.emotion) }}>
                      {r.sentiment.emotion}
                    </span>
                  </div>
                  <div><span className="text-gray-400">Urgency: </span><span className="font-bold text-orange-600">{r.sentiment.urgency}%</span></div>
                  <div>
                    <span className="text-gray-400">Escalate: </span>
                    <span className={`font-semibold ${r.sentiment.escalate ? 'text-red-600' : 'text-green-600'}`}>
                      {r.sentiment.escalate ? 'Yes' : 'No'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Duplicate */}
              <div className="rounded-xl p-3 border border-gray-200 bg-gray-50">
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-xs font-bold text-gray-700 flex items-center gap-1">
                    <Copy size={11} /> Duplicate Check
                  </span>
                  <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">
                    {r.duplicate.confidence}% conf.
                  </span>
                </div>
                <div className="text-xs">
                  {r.duplicate.isDuplicate ? (
                    <span className="text-orange-600 font-medium">Duplicate — {r.duplicate.similar} matching complaint(s) found</span>
                  ) : r.duplicate.similar > 0 ? (
                    <span className="text-blue-600 font-medium">{r.duplicate.similar} related complaint(s) — not a duplicate</span>
                  ) : (
                    <span className="text-green-600 font-medium">No duplicates found — unique complaint</span>
                  )}
                </div>
              </div>

              {/* Compliance */}
              <div className={`rounded-xl p-3 border ${r.compliance.flagged ? 'border-red-200 bg-red-50' : 'border-green-100 bg-green-50'}`}>
                <div className="flex justify-between items-center mb-1.5">
                  <span className={`text-xs font-bold flex items-center gap-1 ${r.compliance.flagged ? 'text-red-800' : 'text-green-800'}`}>
                    <Shield size={11} /> Compliance
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${r.compliance.flagged ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                    {r.compliance.confidence}% conf.
                  </span>
                </div>
                <div className={`text-xs font-medium ${r.compliance.risk === 'HIGH' ? 'text-red-700' : r.compliance.risk === 'MEDIUM' ? 'text-amber-700' : 'text-green-700'}`}>
                  Risk: {r.compliance.risk} — {r.compliance.reason}
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Grounding info */}
        {apiDetail?.grounding_score !== undefined && (
          <section className="rounded-xl p-3 border border-indigo-100 bg-indigo-50 text-xs">
            <div className="font-bold text-indigo-800 mb-1">Accuracy Verification</div>
            <div>
              Response accuracy score: <span className="font-bold text-indigo-700">{Math.round(apiDetail.grounding_score * 100)}%</span>
            </div>
            {apiDetail.grounding_warnings && apiDetail.grounding_warnings.length > 0 && (
              <ul className="mt-1.5 space-y-0.5">
                {apiDetail.grounding_warnings.map((w, i) => (
                  <li key={i} className="text-amber-700">⚠ {w}</li>
                ))}
              </ul>
            )}
          </section>
        )}

        {/* Communication history */}
        {complaint.history.length > 0 && (
          <section>
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Timeline</div>
            <div className="relative pl-5">
              <div className="absolute left-2 top-1 bottom-1 w-px bg-gray-200" />
              {complaint.history.map((h, i) => (
                <div key={i} className="relative mb-3 last:mb-0">
                  <div
                    className="absolute -left-3 top-1.5 w-2.5 h-2.5 rounded-full border-2 border-white"
                    style={{ backgroundColor: getActorColor(h.actor) }}
                  />
                  <div className="text-xs">
                    <span className="font-semibold text-gray-700">{h.actor}</span>
                    <span className="text-gray-400 ml-2">{h.time}</span>
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">{h.action}</div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* AI Draft Response */}
        {(complaint.agentResult.resolution && complaint.agentResult.resolution !== '—') && (
          <section>
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide">AI Draft Response</div>
              <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-medium">AI Generated</span>
            </div>

            {sent ? (
              <div className="rounded-xl p-4 bg-green-50 border border-green-200 text-green-700 text-sm font-medium text-center">
                {feedbackDone === 'accepted' ? '✅ Response approved & sent' : '✅ Response sent successfully'}
              </div>
            ) : feedbackDone === 'rejected' ? (
              <div className="rounded-xl p-4 bg-amber-50 border border-amber-200 text-amber-700 text-sm font-medium text-center">
                Draft rejected. Please write a manual response.
              </div>
            ) : (
              <>
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={9}
                  className="w-full text-xs text-gray-700 border border-gray-200 rounded-xl p-3 resize-none focus:outline-none focus:border-ub-blue leading-relaxed"
                  placeholder="AI draft will appear here after pipeline runs…"
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={handleApprove}
                    disabled={submittingFeedback || !draft}
                    className="flex-1 py-2 rounded-xl text-xs font-semibold text-white bg-ub-blue hover:opacity-90 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-60"
                  >
                    {submittingFeedback ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
                    Approve &amp; Send
                  </button>
                  <button
                    onClick={() => setDraft(complaint.agentResult.resolution)}
                    className="px-3 py-2 rounded-xl text-xs font-medium border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
                    title="Reset to AI draft"
                  >
                    <RotateCcw size={13} />
                  </button>
                  <button
                    onClick={handleReject}
                    disabled={submittingFeedback}
                    className="px-3 py-2 rounded-xl text-xs font-semibold text-white bg-ub-red hover:opacity-90 transition-opacity flex items-center gap-1.5 disabled:opacity-60"
                  >
                    <ArrowUpCircle size={11} /> Escalate
                  </button>
                </div>
                <p className="text-xs text-gray-400 mt-2 text-center">
                  Your feedback helps train the AI for better responses
                </p>
              </>
            )}
          </section>
        )}
      </div>
    </div>
  )
}

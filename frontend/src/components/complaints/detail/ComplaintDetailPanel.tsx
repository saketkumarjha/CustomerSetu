import { useState, useEffect } from 'react'
import {
  X, User, MessageCircle, Copy, Shield, Send,
  RotateCcw, ArrowUpCircle, Loader2, Bot, Clock, CheckCircle2, Play,
} from 'lucide-react'
import type { Complaint } from '../../../types'
import type { ApiComplaint, AgentDecision } from '../../../lib/api'
import { SeverityBadge } from '../../ui/SeverityBadge'
import { ChannelBadge } from '../../ui/ChannelBadge'
import { SlaBadge } from '../../ui/SlaBadge'
import { getInitials, getActorColor } from '../../../utils/styles'
import { api } from '../../../lib/api'

interface Props {
  complaint: Complaint
  onClose: () => void
  loadingDetail?: boolean
  apiDetail?: ApiComplaint | null
  pipelineAvailable?: boolean
  onAfterRunPipeline?: () => void
}

export function ComplaintDetailPanel({
  complaint,
  onClose,
  loadingDetail,
  apiDetail,
  pipelineAvailable = false,
  onAfterRunPipeline,
}: Props) {
  const [draft, setDraft] = useState(complaint.agentResult.resolution)
  const [sent, setSent] = useState(false)
  const [submittingFeedback, setSubmittingFeedback] = useState(false)
  const [feedbackDone, setFeedbackDone] = useState<'accepted' | 'rejected' | null>(null)
  const [agentDecisions, setAgentDecisions] = useState<AgentDecision[]>([])
  const [loadingExplanation, setLoadingExplanation] = useState(false)
  const [pipelineRunLoading, setPipelineRunLoading] = useState(false)
  const [pipelineRunError, setPipelineRunError] = useState<string | null>(null)

  useEffect(() => {
    setDraft(complaint.agentResult.resolution !== '—' ? complaint.agentResult.resolution : '')
    setSent(false)
    setFeedbackDone(null)
    setAgentDecisions([])
    setPipelineRunError(null)
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

  const handleRunPipeline = async () => {
    if (!pipelineAvailable) return
    setPipelineRunError(null)
    setPipelineRunLoading(true)
    try {
      await api.pipeline.run(complaint.id)
      onAfterRunPipeline?.()
    } catch (e) {
      setPipelineRunError(e instanceof Error ? e.message : 'Could not start the pipeline')
    } finally {
      setPipelineRunLoading(false)
    }
  }

  return (
    <div className="w-full lg:w-[460px] lg:min-w-[460px] flex flex-col bg-white lg:border-l border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 bg-ub-blue flex-shrink-0">
        <div>
          <div className="text-white font-bold text-sm font-mono">{complaint.id}</div>
          <div className="text-blue-200/90 text-xs">Complaint detail</div>
        </div>
        <div className="flex items-center gap-2">
          {loadingDetail && <Loader2 size={14} className="text-blue-200 animate-spin" />}
          {apiDetail?.pipeline_status === 'complete' && (
            <span className="text-xs bg-white/15 text-white px-2 py-0.5 rounded-md border border-white/20">
              Analysis complete
            </span>
          )}
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-md bg-white/15 text-white flex items-center justify-center hover:bg-white/25 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="overflow-y-auto flex-1 p-4 space-y-4">

        {/* Customer info */}
        <section className="rounded-xl p-3 border border-slate-200/90 bg-white/70 backdrop-blur-sm">
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
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-gray-400">Channel: </span>
              <ChannelBadge channel={complaint.channel} />
            </div>
            <div><span className="text-gray-400">Date: </span><span className="font-medium">{complaint.date}</span></div>
            <div className="flex items-center gap-1.5">
              <span className="text-gray-400">Severity: </span>
              <SeverityBadge severity={complaint.severity} />
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-gray-400">SLA: </span>
              <SlaBadge breached={complaint.slaBreached} label={complaint.slaRemaining} />
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
            <p className="text-xs text-slate-600 mt-1 bg-slate-50 px-2 py-1 rounded-md border border-slate-200/80">
              Language: <strong>{apiDetail.language.toUpperCase()}</strong> (translated automatically)
            </p>
          )}
        </section>

        {/* AI analysis — use explanation_trace if available, else use agentResult */}
        <section>
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Bot size={11} /> Analysis
            {loadingExplanation && <Loader2 size={10} className="animate-spin text-gray-400" />}
          </div>

          {/* Live explanation trace from backend */}
          {agentDecisions.length > 0 ? (
            <div className="space-y-2">
              {agentDecisions.map((d) => (
                <div key={d.agent_name} className={`rounded-md p-3 border text-xs ${
                  d.status === 'complete' ? 'border-slate-200 bg-white/80'
                  : d.status === 'failed' ? 'border-ub-red/30 bg-ub-red/5'
                  : 'border-slate-200 bg-slate-50/80'
                }`}>
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="font-semibold text-slate-800 flex items-center gap-1">
                      <CheckCircle2 size={10} className="text-slate-500" />
                      {d.agent_name}
                    </span>
                    <div className="flex items-center gap-2">
                      {d.confidence !== undefined && (
                        <span className="text-slate-500">{Math.round(d.confidence * 100)}% confidence</span>
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
                        <span key={ev} className="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded-md text-xs border border-slate-200/80">
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
              <div className="rounded-md p-3 border border-slate-200 bg-white/80">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-semibold text-slate-800">Classification</span>
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md border border-slate-200/80">
                    {r.classification.confidence}% confidence
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <div><span className="text-gray-400">Category: </span><span className="font-medium">{r.classification.category}</span></div>
                  <div><span className="text-gray-400">Product: </span><span className="font-medium">{r.classification.product}</span></div>
                  <div className="col-span-2"><span className="text-gray-400">Type: </span><span className="font-medium">{r.classification.type}</span></div>
                </div>
              </div>

              {/* Sentiment */}
              <div className="rounded-md p-3 border border-slate-200 bg-slate-50/50">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-semibold text-slate-800 flex items-center gap-1">
                    <MessageCircle size={11} /> Sentiment
                  </span>
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md border border-slate-200/80">
                    {r.sentiment.confidence}% confidence
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1 text-xs">
                  <div>
                    <span className="text-slate-500">Emotion: </span>
                    <span className="font-medium text-slate-800">
                      {r.sentiment.emotion}
                    </span>
                  </div>
                  <div><span className="text-slate-500">Urgency: </span><span className="font-medium text-slate-800">{r.sentiment.urgency}%</span></div>
                  <div>
                    <span className="text-slate-500">Escalate: </span>
                    <span className="font-medium text-slate-800">
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
                    <span className="text-ub-red font-medium">Possible duplicate — {r.duplicate.similar} similar case(s)</span>
                  ) : r.duplicate.similar > 0 ? (
                    <span className="text-slate-700 font-medium">{r.duplicate.similar} related case(s), not marked duplicate</span>
                  ) : (
                    <span className="text-slate-700 font-medium">No duplicate match</span>
                  )}
                </div>
              </div>

              {/* Compliance */}
              <div className={`rounded-md p-3 border ${r.compliance.flagged ? 'border-ub-red/25 bg-ub-red/5' : 'border-slate-200 bg-white/80'}`}>
                <div className="flex justify-between items-center mb-1.5">
                  <span className={`text-xs font-semibold flex items-center gap-1 ${r.compliance.flagged ? 'text-ub-red' : 'text-slate-800'}`}>
                    <Shield size={11} /> Compliance
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-md border ${r.compliance.flagged ? 'bg-white border-ub-red/20 text-ub-red' : 'bg-slate-100 border-slate-200 text-slate-600'}`}>
                    {r.compliance.confidence}% confidence
                  </span>
                </div>
                <div className={`text-xs font-medium ${r.compliance.flagged ? 'text-ub-red' : 'text-slate-700'}`}>
                  Risk: {r.compliance.risk} — {r.compliance.reason}
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Grounding info */}
        {apiDetail?.grounding_score !== undefined && (
          <section className="rounded-md p-3 border border-slate-200 bg-slate-50/80 text-xs text-slate-700">
            <div className="font-semibold text-slate-800 mb-1">Source check</div>
            <div>
              Match score: <span className="font-semibold text-ub-blue">{Math.round(apiDetail.grounding_score * 100)}%</span>
            </div>
            {apiDetail.grounding_warnings && apiDetail.grounding_warnings.length > 0 && (
              <ul className="mt-1.5 space-y-0.5">
                {apiDetail.grounding_warnings.map((w, i) => (
                  <li key={i} className="text-slate-600">{w}</li>
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
              <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md border border-slate-200/80 font-medium">Suggested reply</span>
            </div>

            {sent ? (
              <div className="rounded-md p-4 bg-slate-50 border border-slate-200 text-slate-800 text-sm font-medium text-center">
                {feedbackDone === 'accepted' ? 'Approved and sent.' : 'Sent successfully.'}
              </div>
            ) : feedbackDone === 'rejected' ? (
              <div className="rounded-md p-4 bg-amber-50 border border-amber-200/80 text-amber-900 text-sm font-medium text-center">
                Draft declined. Please reply manually.
              </div>
            ) : (
              <>
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={9}
                  className="w-full text-xs text-gray-700 border border-gray-200 rounded-md p-3 resize-none focus:outline-none focus:border-ub-blue leading-relaxed"
                  placeholder="AI draft will appear here after pipeline runs…"
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={handleApprove}
                    disabled={submittingFeedback || !draft}
                    className="flex-1 py-2 rounded-md text-xs font-semibold text-white bg-ub-blue hover:opacity-90 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-60"
                  >
                    {submittingFeedback ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
                    Approve &amp; Send
                  </button>
                  <button
                    onClick={() => setDraft(complaint.agentResult.resolution)}
                    className="px-3 py-2 rounded-md text-xs font-medium border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
                    title="Reset to AI draft"
                  >
                    <RotateCcw size={13} />
                  </button>
                  <button
                    onClick={handleReject}
                    disabled={submittingFeedback}
                    className="px-3 py-2 rounded-md text-xs font-semibold text-white bg-ub-red hover:opacity-90 transition-opacity flex items-center gap-1.5 disabled:opacity-60"
                  >
                    <ArrowUpCircle size={11} /> Escalate
                  </button>
                </div>
                <p className="text-xs text-gray-400 mt-2 text-center">
                  Feedback improves future suggestions.
                </p>
              </>
            )}
          </section>
        )}

        {/* Run AI pipeline — end of detail panel */}
        <section className="rounded-xl border border-slate-200 bg-slate-50/90 p-4 mt-1">
          <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5">AI pipeline</div>
          <p className="text-xs text-slate-500 mb-3 leading-relaxed">
            Run the full multi-agent analysis on this complaint. Progress streams on the AI Pipeline tab.
          </p>
          {pipelineAvailable ? (
            <>
              <button
                type="button"
                onClick={handleRunPipeline}
                disabled={pipelineRunLoading}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-md text-xs font-semibold text-white bg-ub-blue hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
              >
                {pipelineRunLoading ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Play size={14} />
                )}
                {pipelineRunLoading ? 'Starting…' : 'Run AI pipeline'}
              </button>
              {pipelineRunError && (
                <p className="text-xs text-ub-red mt-2">{pipelineRunError}</p>
              )}
            </>
          ) : (
            <p className="text-xs text-slate-400">
              Connect to the live API to run analysis on real complaints.
            </p>
          )}
        </section>
      </div>
    </div>
  )
}

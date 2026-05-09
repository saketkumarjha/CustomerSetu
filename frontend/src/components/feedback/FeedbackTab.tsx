import { useState, type FormEvent } from 'react'
import {
  MessageSquareHeart,
  RefreshCw,
  Download,
  Send,
  Bell,
  Loader2,
  Database,
  Sparkles,
} from 'lucide-react'
import {
  api,
  type DatasetExportPreviewResponse,
  type DatasetExportDownloadResult,
} from '../../lib/api'
import { useApiData } from '../../hooks/useApiData'

const ISSUE_TAGS = [
  { id: 'too_slow', label: 'Too slow' },
  { id: 'wrong_solution', label: 'Wrong solution' },
  { id: 'rude', label: 'Rude / poor tone' },
  { id: 'incomplete', label: 'Incomplete' },
] as const

export function FeedbackTab() {
  const { data: stats, loading: statsLoading, error: statsError, refetch: refetchStats } = useApiData(
    () => api.feedback.datasetStats(),
    [],
  )

  const {
    data: datasetList,
    loading: rowsLoading,
    error: rowsError,
    refetch: refetchRows,
  } = useApiData(() => api.feedback.datasetRecords(50), [])

  const [minScore, setMinScore] = useState('')
  const [exportCategory, setExportCategory] = useState('')
  const [onlyAccepted, setOnlyAccepted] = useState(false)
  const [previewData, setPreviewData] = useState<DatasetExportPreviewResponse | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)

  const [downloadLoading, setDownloadLoading] = useState(false)
  const [downloadMessage, setDownloadMessage] = useState<string | null>(null)

  const [surveyComplaintId, setSurveyComplaintId] = useState('')
  const [surveyLoading, setSurveyLoading] = useState(false)
  const [surveyResult, setSurveyResult] = useState<string | null>(null)
  const [surveyError, setSurveyError] = useState<string | null>(null)

  const [cfComplaintId, setCfComplaintId] = useState('')
  const [cfCustomerId, setCfCustomerId] = useState('')
  const [cfRating, setCfRating] = useState(5)
  const [cfTags, setCfTags] = useState<string[]>([])
  const [cfText, setCfText] = useState('')
  const [cfLoading, setCfLoading] = useState(false)
  const [cfMessage, setCfMessage] = useState<string | null>(null)
  const [cfError, setCfError] = useState<string | null>(null)

  const parseMinScore = (): number | undefined => {
    const n = parseFloat(minScore)
    if (Number.isNaN(n) || n <= 0) return undefined
    return n
  }

  const handlePreview = async () => {
    setPreviewLoading(true)
    setPreviewError(null)
    try {
      const data = await api.feedback.exportDatasetPreview({
        minCombinedScore: parseMinScore(),
        category: exportCategory || undefined,
        onlyAgentAccepted: onlyAccepted,
      })
      setPreviewData(data)
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : 'Preview failed')
      setPreviewData(null)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleDownload = async () => {
    setDownloadLoading(true)
    setDownloadMessage(null)
    try {
      const result: DatasetExportDownloadResult = await api.feedback.exportDatasetDownload({
        minCombinedScore: parseMinScore(),
        category: exportCategory || undefined,
        onlyAgentAccepted: onlyAccepted,
      })
      if ('downloaded' in result && result.downloaded) {
        setDownloadMessage(
          `Downloaded ${result.filename}${result.recordCount != null ? ` (${result.recordCount} rows)` : ''}. Marked as exported on server.`,
        )
        refetchStats()
        refetchRows()
      } else if ('message' in result) {
        setDownloadMessage(result.message + (result.hint ? ` — ${result.hint}` : ''))
      }
    } catch (e) {
      setDownloadMessage(e instanceof Error ? e.message : 'Download failed')
    } finally {
      setDownloadLoading(false)
    }
  }

  const handleTriggerSurvey = async () => {
    const id = surveyComplaintId.trim()
    if (!id) {
      setSurveyError('Enter a complaint ID')
      return
    }
    setSurveyLoading(true)
    setSurveyError(null)
    setSurveyResult(null)
    try {
      const r = await api.feedback.triggerSurvey(id)
      setSurveyResult(r.message)
    } catch (e) {
      setSurveyError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setSurveyLoading(false)
    }
  }

  const toggleTag = (id: string) => {
    setCfTags((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]))
  }

  const handleCustomerSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setCfLoading(true)
    setCfMessage(null)
    setCfError(null)
    try {
      const res = await api.feedback.submitCustomer({
        complaint_id: cfComplaintId.trim(),
        customer_id: cfCustomerId.trim(),
        rating: cfRating,
        issue_tags: cfTags,
        feedback_text: cfText.trim() || undefined,
      })
      setCfMessage(res.message)
      refetchStats()
      refetchRows()
    } catch (err) {
      setCfError(err instanceof Error ? err.message : 'Submit failed')
    } finally {
      setCfLoading(false)
    }
  }

  const readiness = stats?.fine_tuning_readiness

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-50 flex items-center justify-center">
            <MessageSquareHeart size={20} className="text-violet-700" />
          </div>
          <div>
            <h1 className="text-base font-bold text-gray-800">Feedback &amp; training data</h1>
            <p className="text-xs text-gray-500">
              Agent feedback is captured from the complaint detail panel. Here you can trigger CSAT surveys, submit
              customer ratings, inspect the fine-tune dataset, and export JSONL.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            refetchStats()
            refetchRows()
            setPreviewData(null)
          }}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50"
        >
          <RefreshCw size={12} /> Refresh stats
        </button>
      </div>

      {/* Dataset stats */}
      {statsLoading && (
        <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center text-sm text-gray-400">
          Loading dataset statistics…
        </div>
      )}

      {statsError && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-amber-900">
          Could not load dataset stats. Ensure the backend is running.
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Total records</div>
            <div className="text-2xl font-bold text-gray-800">{stats.total_records}</div>
            {stats.message && stats.total_records === 0 && (
              <p className="text-xs text-gray-500 mt-2">{stats.message}</p>
            )}
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Unexported</div>
            <div className="text-2xl font-bold text-ub-blue">{stats.unexported_records ?? '—'}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Avg combined score</div>
            <div className="text-2xl font-bold text-gray-800">
              {stats.avg_combined_score != null ? stats.avg_combined_score : '—'}
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Readiness</div>
            <div className="text-sm font-semibold text-gray-800 leading-snug">
              {readiness?.status ?? stats.message ?? '—'}
            </div>
            {readiness && (
              <div className="mt-2 h-2 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full bg-violet-600 rounded-full transition-all"
                  style={{ width: `${Math.min(100, readiness.percentage)}%` }}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Individual rows — same source as "Total records" count */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Database size={16} className="text-violet-600" />
          <h2 className="text-sm font-bold text-gray-700">Training rows</h2>
          {datasetList != null && (
            <span className="text-xs text-gray-400 ml-auto">{datasetList.count} shown (max {datasetList.limit})</span>
          )}
        </div>
        <p className="text-xs text-gray-600 leading-relaxed bg-violet-50/80 border border-violet-100 rounded-lg px-3 py-2">
          <strong>Where the number comes from:</strong> each row is stored in the{' '}
          <code className="bg-white/80 px-1 rounded border border-violet-100">fine_tune_dataset</code> table after you use{' '}
          <strong>Approve &amp; Send</strong> or <strong>Escalate</strong> on a complaint’s AI draft (All Complaints → open a
          complaint). The backend saves that feedback asynchronously for model fine-tuning. Customer CSAT updates the same
          rows when ratings arrive.
        </p>
        {datasetList?.source_note && (
          <p className="text-xs text-gray-500 italic">{datasetList.source_note}</p>
        )}
        {rowsLoading && (
          <div className="flex items-center gap-2 text-xs text-gray-400 py-4">
            <Loader2 size={14} className="animate-spin" /> Loading rows…
          </div>
        )}
        {rowsError && (
          <p className="text-xs text-ub-red bg-ub-red/5 border border-ub-red/10 rounded-lg px-3 py-2">{rowsError}</p>
        )}
        {!rowsLoading && datasetList && datasetList.records.length === 0 && (
          <p className="text-xs text-gray-500">No training rows yet — submit agent feedback from a complaint detail first.</p>
        )}
        {!rowsLoading && datasetList && datasetList.records.length > 0 && (
          <div className="overflow-x-auto border border-gray-100 rounded-xl">
            <table className="w-full text-xs min-w-[720px]">
              <thead>
                <tr className="text-gray-400 font-semibold uppercase tracking-wide border-b border-gray-100 bg-gray-50/80">
                  <th className="text-left py-2 px-3">Complaint ID</th>
                  <th className="text-left py-2 px-3">Category</th>
                  <th className="text-right py-2 px-3">Agent</th>
                  <th className="text-right py-2 px-3">Customer</th>
                  <th className="text-right py-2 px-3">Combined</th>
                  <th className="text-center py-2 px-3">Exported</th>
                  <th className="text-left py-2 px-3">Created</th>
                  <th className="text-left py-2 px-3">Complaint preview</th>
                </tr>
              </thead>
              <tbody>
                {datasetList.records.map((row) => (
                  <tr key={String(row.id)} className="border-b border-gray-50 align-top">
                    <td className="py-2 px-3 font-mono font-semibold text-ub-blue">{row.complaint_id}</td>
                    <td className="py-2 px-3 text-gray-700">{row.category ?? '—'}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{row.agent_rating ?? '—'}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{row.customer_rating ?? '—'}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{row.combined_score ?? '—'}</td>
                    <td className="py-2 px-3 text-center">{row.exported ? 'Yes' : 'No'}</td>
                    <td className="py-2 px-3 text-gray-500 whitespace-nowrap">
                      {row.created_at
                        ? (() => {
                            try {
                              return new Date(row.created_at).toLocaleString('en-IN', {
                                dateStyle: 'short',
                                timeStyle: 'short',
                              })
                            } catch {
                              return row.created_at
                            }
                          })()
                        : '—'}
                    </td>
                    <td className="py-2 px-3 text-gray-600 max-w-[280px] leading-relaxed">{row.complaint_preview || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {stats?.quality_breakdown && (
        <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Database size={16} className="text-gray-500" />
            <h2 className="text-sm font-bold text-gray-700">Quality breakdown (agent scores)</h2>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center text-xs">
            <div className="rounded-lg bg-green-50 border border-green-100 p-3">
              <div className="text-lg font-bold text-green-800">
                {stats.quality_breakdown['accepted_agent_1.0']}
              </div>
              <div className="text-green-700">Accepted (1.0)</div>
            </div>
            <div className="rounded-lg bg-amber-50 border border-amber-100 p-3">
              <div className="text-lg font-bold text-amber-900">
                {stats.quality_breakdown['edited_agent_0.5']}
              </div>
              <div className="text-amber-800">Edited (0.5)</div>
            </div>
            <div className="rounded-lg bg-red-50 border border-red-100 p-3">
              <div className="text-lg font-bold text-red-800">
                {stats.quality_breakdown['rejected_agent_0.0']}
              </div>
              <div className="text-red-700">Rejected (0.0)</div>
            </div>
          </div>
          {stats.next_steps && (
            <p className="text-xs text-gray-500 mt-3 flex items-start gap-1.5">
              <Sparkles size={12} className="text-violet-500 mt-0.5 flex-shrink-0" />
              {stats.next_steps}
            </p>
          )}
        </div>
      )}

      {/* Export JSONL */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm space-y-4">
        <div className="flex items-center gap-2">
          <Download size={16} className="text-gray-500" />
          <h2 className="text-sm font-bold text-gray-700">Export fine-tuning dataset (JSONL)</h2>
        </div>
        <p className="text-xs text-gray-500 leading-relaxed">
          Exports <strong>unexported</strong> rows from <code className="bg-gray-100 px-1 rounded">fine_tune_dataset</code>.
          Download streams a JSONL file and marks those rows exported. Use preview to estimate rows before downloading.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label className="text-xs">
            <span className="text-gray-500 block mb-1">Min combined score (optional)</span>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              placeholder="0 = all"
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="text-xs sm:col-span-2">
            <span className="text-gray-500 block mb-1">Category filter (optional)</span>
            <input
              type="text"
              placeholder="e.g. General Banking"
              value={exportCategory}
              onChange={(e) => setExportCategory(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </label>
        </div>
        <label className="flex items-center gap-2 text-xs text-gray-700 cursor-pointer">
          <input
            type="checkbox"
            checked={onlyAccepted}
            onChange={(e) => setOnlyAccepted(e.target.checked)}
            className="rounded border-gray-300"
          />
          Only agent-accepted rows (agent_rating = 1.0)
        </label>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void handlePreview()}
            disabled={previewLoading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {previewLoading ? <Loader2 size={14} className="animate-spin" /> : null}
            Preview export
          </button>
          <button
            type="button"
            onClick={() => void handleDownload()}
            disabled={downloadLoading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-700 text-white text-xs font-semibold hover:bg-violet-800 disabled:opacity-50"
          >
            {downloadLoading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Download JSONL
          </button>
        </div>
        {previewError && <p className="text-xs text-ub-red">{previewError}</p>}
        {downloadMessage && <p className="text-xs text-gray-600 bg-gray-50 border border-gray-100 rounded-lg p-3">{downloadMessage}</p>}
        {previewData && (
          <pre className="text-[11px] bg-slate-900 text-slate-100 rounded-lg p-3 overflow-x-auto max-h-56 overflow-y-auto">
            {JSON.stringify(previewData, null, 2)}
          </pre>
        )}
      </div>

      {/* Trigger CSAT survey */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm space-y-3">
        <div className="flex items-center gap-2">
          <Bell size={16} className="text-amber-600" />
          <h2 className="text-sm font-bold text-gray-700">Trigger CSAT survey (simulated)</h2>
        </div>
        <p className="text-xs text-gray-500">
          Sets complaint status to <code className="bg-gray-100 px-1 rounded">awaiting_feedback</code>. Pipeline must be
          complete. In production this would email/SMS the customer — here it is a demo hook.
        </p>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            placeholder="Complaint ID"
            value={surveyComplaintId}
            onChange={(e) => setSurveyComplaintId(e.target.value)}
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
          />
          <button
            type="button"
            onClick={() => void handleTriggerSurvey()}
            disabled={surveyLoading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-amber-600 text-white text-xs font-semibold hover:bg-amber-700 disabled:opacity-50"
          >
            {surveyLoading ? <Loader2 size={14} className="animate-spin" /> : <Bell size={14} />}
            Trigger survey
          </button>
        </div>
        {surveyError && <p className="text-xs text-ub-red">{surveyError}</p>}
        {surveyResult && <p className="text-xs text-green-800 bg-green-50 border border-green-100 rounded-lg p-3">{surveyResult}</p>}
      </div>

      {/* Customer CSAT */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Send size={16} className="text-ub-blue" />
          <h2 className="text-sm font-bold text-gray-700">Submit customer CSAT</h2>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          Use after a survey is triggered (or for testing). Rating 1–5; optional tags and text (PII is masked server-side).
        </p>
        <form onSubmit={handleCustomerSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-xs">
              <span className="text-gray-500 block mb-1">Complaint ID</span>
              <input
                required
                value={cfComplaintId}
                onChange={(e) => setCfComplaintId(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              />
            </label>
            <label className="text-xs">
              <span className="text-gray-500 block mb-1">Customer ID</span>
              <input
                required
                value={cfCustomerId}
                onChange={(e) => setCfCustomerId(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              />
            </label>
          </div>
          <label className="text-xs block">
            <span className="text-gray-500 block mb-1">Rating (1 = very dissatisfied, 5 = very satisfied)</span>
            <select
              value={cfRating}
              onChange={(e) => setCfRating(Number(e.target.value))}
              className="w-full sm:w-48 border border-gray-200 rounded-lg px-3 py-2 text-sm"
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <div>
            <span className="text-xs text-gray-500 block mb-2">Issue tags (optional)</span>
            <div className="flex flex-wrap gap-2">
              {ISSUE_TAGS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => toggleTag(t.id)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    cfTags.includes(t.id)
                      ? 'bg-ub-blue text-white border-ub-blue'
                      : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <label className="text-xs block">
            <span className="text-gray-500 block mb-1">Feedback text (optional)</span>
            <textarea
              value={cfText}
              onChange={(e) => setCfText(e.target.value)}
              rows={3}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none"
              placeholder="Brief comment…"
            />
          </label>
          {cfError && <p className="text-xs text-ub-red">{cfError}</p>}
          {cfMessage && <p className="text-xs text-green-800 bg-green-50 border border-green-100 rounded-lg p-3">{cfMessage}</p>}
          <button
            type="submit"
            disabled={cfLoading}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-ub-blue text-white text-xs font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {cfLoading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Submit CSAT
          </button>
        </form>
      </div>
    </div>
  )
}

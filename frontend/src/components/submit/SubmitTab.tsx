import { useState, useRef, useCallback } from 'react'
import {
  Send, Upload, X, FileImage, CheckCircle2, AlertCircle,
  ChevronRight, Loader2, Bot,
} from 'lucide-react'
import { api, createPipelineStream } from '../../lib/api'
import { attachPipelineEventSource } from '../../lib/pipelineSse'
import type { PipelineSSEEvent, TabId } from '../../types'

const CHANNELS = ['Email', 'Phone', 'Web Form', 'Mobile App', 'Social Media']

interface AgentStep {
  name: string
  order: number
  status: 'waiting' | 'processing' | 'complete' | 'failed'
  decision?: string
  confidence?: number
  duration_ms?: number
}

interface Props {
  setActive: (id: TabId) => void
}

type FlowState = 'form' | 'submitting' | 'pipeline' | 'done' | 'error'

export function SubmitTab({ setActive }: Props) {
  const [complaintText, setComplaintText] = useState('')
  const [channel, setChannel] = useState('Email')
  const [customerId, setCustomerId] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const [flowState, setFlowState] = useState<FlowState>('form')
  const [complaintId, setComplaintId] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([])
  const [pipelineResult, setPipelineResult] = useState<{ route?: string; category?: string } | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const detachSseRef = useRef<(() => void) | null>(null)
  /** Avoid treating EventSource close-after-success as a hard error */
  const sseActiveRef = useRef(false)

  const handleImageDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('image/')) setImageFile(file)
  }, [])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setImageFile(file)
  }

  const canSubmit = complaintText.trim().length >= 10 && customerId.trim().length >= 2

  const updateAgent = (event: PipelineSSEEvent) => {
    if (!event.agent || event.order == null) return
    const rawStatus = String(event.status ?? '').toLowerCase()
    setAgentSteps((prev) => {
      const existing = prev.findIndex((a) => a.name === event.agent)
      const step: AgentStep = {
        name: event.agent!,
        order: event.order!,
        status:
          rawStatus === 'processing'
            ? 'processing'
            : rawStatus === 'complete'
            ? 'complete'
            : rawStatus === 'failed'
            ? 'failed'
            : 'waiting',
        decision: event.decision,
        confidence: event.confidence,
        duration_ms: event.duration_ms,
      }
      if (existing >= 0) {
        const updated = [...prev]
        updated[existing] = step
        return updated
      }
      return [...prev, step].sort((a, b) => a.order - b.order)
    })
  }

  const startStream = (cid: string) => {
    detachSseRef.current?.()
    detachSseRef.current = null
    esRef.current?.close()
    sseActiveRef.current = true

    const es = createPipelineStream(cid)
    esRef.current = es

    detachSseRef.current = attachPipelineEventSource(es, {
      onAgentUpdate: updateAgent,
      onPipelineComplete: (d) => {
        sseActiveRef.current = false
        setPipelineResult({
          route: typeof d.route === 'string' ? d.route : undefined,
          category: typeof d.category === 'string' ? d.category : undefined,
        })
        setFlowState('done')
        detachSseRef.current?.()
        detachSseRef.current = null
        es.close()
      },
      onPipelineError: (p) => {
        sseActiveRef.current = false
        setFlowState('error')
        setErrorMsg(p.error ?? 'AI analysis encountered an error. Check backend logs.')
        detachSseRef.current?.()
        detachSseRef.current = null
        es.close()
      },
      onTransportError: () => {
        if (!sseActiveRef.current) return
        sseActiveRef.current = false
        setFlowState('error')
        setErrorMsg(
          'Lost connection to the AI pipeline. Check backend is running, VITE_API_KEY matches API_KEY, and browser Network tab for the stream request.',
        )
        detachSseRef.current?.()
        detachSseRef.current = null
        es.close()
      },
      onLog: (line) => console.info('[Submit pipeline]', line),
    })
  }

  const handleSubmit = async () => {
    if (!canSubmit) return
    setFlowState('submitting')
    setErrorMsg(null)
    setAgentSteps([])

    const idempotencyKey = crypto.randomUUID()
    const form = new FormData()
    form.append('complaint_text', complaintText.trim())
    form.append('channel', channel)
    form.append('customer_id', customerId.trim())
    if (imageFile) form.append('image', imageFile)

    try {
      const res = await api.complaints.submit(form, idempotencyKey)
      setComplaintId(res.complaint_id)

      // Trigger pipeline
      await api.pipeline.run(res.complaint_id)

      // Start SSE stream
      setFlowState('pipeline')
      startStream(res.complaint_id)
    } catch (e) {
      setFlowState('error')
      setErrorMsg(e instanceof Error ? e.message : 'Something went wrong. Please try again.')
    }
  }

  const reset = () => {
    sseActiveRef.current = false
    detachSseRef.current?.()
    detachSseRef.current = null
    esRef.current?.close()
    setFlowState('form')
    setComplaintText('')
    setChannel('Email')
    setCustomerId('')
    setImageFile(null)
    setComplaintId(null)
    setAgentSteps([])
    setPipelineResult(null)
    setErrorMsg(null)
  }

  if (flowState === 'error') {
    return (
      <div className="max-w-xl mx-auto mt-12 text-center">
        <div className="bg-red-50 border border-red-200 rounded-2xl p-8">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-red-800 mb-2">Something went wrong</h2>
          <p className="text-sm text-red-600 mb-6">{errorMsg}</p>
          <button onClick={reset} className="px-6 py-2.5 rounded-lg bg-ub-blue text-white text-sm font-semibold hover:opacity-90">
            Try Again
          </button>
        </div>
      </div>
    )
  }

  if (flowState === 'pipeline' || flowState === 'done') {
    const processing = agentSteps.filter((s) => s.status === 'processing')
    const done = agentSteps.filter((s) => s.status === 'complete')

    return (
      <div className="max-w-2xl mx-auto space-y-4">
        {/* Header card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-xs text-green-600 font-semibold uppercase tracking-wide">
                  {flowState === 'done' ? 'Analysis Complete' : 'AI Analysis Running'}
                </span>
              </div>
              <h2 className="text-lg font-bold text-gray-800">Complaint Registered</h2>
              <p className="text-sm text-gray-500 mt-0.5 font-mono">{complaintId}</p>
            </div>
            {flowState === 'done' && (
              <CheckCircle2 className="w-10 h-10 text-green-500 flex-shrink-0" />
            )}
            {flowState === 'pipeline' && (
              <Loader2 className="w-10 h-10 text-ub-blue animate-spin flex-shrink-0" />
            )}
          </div>
        </div>

        {/* Agent progress */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Bot size={16} className="text-ub-blue" />
            <span className="text-sm font-bold text-gray-700">AI Agents Working</span>
            {flowState === 'pipeline' && (
              <span className="text-xs text-gray-400 ml-auto">{done.length} of {agentSteps.length} complete</span>
            )}
          </div>

          {agentSteps.length === 0 && flowState === 'pipeline' && (
            <div className="flex items-center gap-2 text-sm text-gray-400 py-4">
              <Loader2 size={14} className="animate-spin" /> Starting AI agents…
            </div>
          )}

          <div className="space-y-2">
            {agentSteps.map((step) => (
              <div
                key={step.name}
                className={`rounded-xl p-3 border transition-all ${
                  step.status === 'complete'
                    ? 'border-green-200 bg-green-50'
                    : step.status === 'processing'
                    ? 'border-blue-200 bg-blue-50'
                    : step.status === 'failed'
                    ? 'border-red-200 bg-red-50'
                    : 'border-gray-100 bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    {step.status === 'complete' && <CheckCircle2 size={14} className="text-green-600 flex-shrink-0" />}
                    {step.status === 'processing' && <Loader2 size={14} className="animate-spin text-blue-600 flex-shrink-0" />}
                    {step.status === 'failed' && <AlertCircle size={14} className="text-red-500 flex-shrink-0" />}
                    {step.status === 'waiting' && <div className="w-3.5 h-3.5 rounded-full border-2 border-gray-300 flex-shrink-0" />}
                    <span className="text-xs font-semibold text-gray-700 truncate">{step.name}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {step.confidence !== undefined && (
                      <span className="text-xs text-gray-400">{Math.round(step.confidence * 100)}% confident</span>
                    )}
                    {step.duration_ms && (
                      <span className="text-xs text-gray-400">{step.duration_ms}ms</span>
                    )}
                    {step.status === 'processing' && (
                      <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">Processing…</span>
                    )}
                  </div>
                </div>
                {step.decision && step.status === 'complete' && (
                  <p className="text-xs text-gray-600 mt-1.5 ml-5">
                    Result: <span className="font-semibold text-gray-800">{step.decision}</span>
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Final result */}
        {flowState === 'done' && pipelineResult && (
          <div className="bg-white rounded-2xl shadow-sm border border-green-200 p-5">
            <h3 className="text-sm font-bold text-gray-700 mb-3">Analysis Summary</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {pipelineResult.category && (
                <div className="bg-blue-50 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-0.5">Category</div>
                  <div className="font-semibold text-gray-800">{pipelineResult.category}</div>
                </div>
              )}
              {pipelineResult.route && (
                <div className={`rounded-lg p-3 ${pipelineResult.route === 'auto_respond' ? 'bg-green-50' : 'bg-amber-50'}`}>
                  <div className="text-xs text-gray-400 mb-0.5">Action</div>
                  <div className={`font-semibold ${pipelineResult.route === 'auto_respond' ? 'text-green-700' : 'text-amber-700'}`}>
                    {pipelineResult.route === 'auto_respond' ? '✅ Auto Response Sent' : '👤 Needs Your Review'}
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-4">
              <button
                onClick={() => { setActive('complaints') }}
                className="flex-1 py-2.5 rounded-lg bg-ub-blue text-white text-sm font-semibold hover:opacity-90 flex items-center justify-center gap-1.5"
              >
                View in Complaints <ChevronRight size={14} />
              </button>
              <button
                onClick={reset}
                className="px-4 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
              >
                Submit New
              </button>
            </div>
          </div>
        )}

        {processing.length === 0 && flowState === 'pipeline' && agentSteps.length > 0 && (
          <p className="text-xs text-center text-gray-400">Waiting for next agent…</p>
        )}
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {/* Page header */}
      <div className="bg-ub-blue rounded-2xl p-5 text-white">
        <h1 className="text-lg font-bold mb-1">Register New Complaint</h1>
        <p className="text-blue-200 text-sm">
          Fill in the customer details below. Our AI will automatically analyse and route the complaint.
        </p>
      </div>

      {/* Form */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 space-y-4">
        {/* Customer ID */}
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">
            Customer ID <span className="text-red-500">*</span>
          </label>
          <input
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            placeholder="e.g. CUST-00123 or phone number"
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-ub-blue"
          />
        </div>

        {/* Channel */}
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">
            Received Via <span className="text-red-500">*</span>
          </label>
          <div className="flex flex-wrap gap-2">
            {CHANNELS.map((ch) => (
              <button
                key={ch}
                onClick={() => setChannel(ch)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                  channel === ch
                    ? 'bg-ub-blue text-white border-ub-blue'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                {ch}
              </button>
            ))}
          </div>
        </div>

        {/* Complaint text */}
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">
            Customer's Complaint <span className="text-red-500">*</span>
          </label>
          <textarea
            value={complaintText}
            onChange={(e) => setComplaintText(e.target.value)}
            placeholder="Type or paste the customer's complaint here. Include account numbers, transaction IDs, dates, and amounts if mentioned."
            rows={6}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-ub-blue resize-none leading-relaxed"
          />
          <div className="flex justify-between mt-1">
            <span className="text-xs text-gray-400">Minimum 10 characters</span>
            <span className={`text-xs ${complaintText.length < 10 ? 'text-gray-300' : 'text-green-600'}`}>
              {complaintText.length} characters
            </span>
          </div>
        </div>

        {/* Image upload */}
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">
            Attach Screenshot / Document <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleImageDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
              dragOver
                ? 'border-ub-blue bg-blue-50'
                : imageFile
                ? 'border-green-400 bg-green-50'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            {imageFile ? (
              <div className="flex items-center justify-center gap-3">
                <FileImage size={20} className="text-green-600" />
                <span className="text-sm font-medium text-green-700">{imageFile.name}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); setImageFile(null) }}
                  className="w-5 h-5 rounded-full bg-gray-200 flex items-center justify-center hover:bg-gray-300"
                >
                  <X size={10} />
                </button>
              </div>
            ) : (
              <div>
                <Upload size={20} className="text-gray-400 mx-auto mb-2" />
                <p className="text-xs text-gray-500">
                  Drag & drop an image here, or <span className="text-ub-blue font-medium">click to browse</span>
                </p>
                <p className="text-xs text-gray-400 mt-1">JPG, PNG, WEBP up to 10MB</p>
              </div>
            )}
          </div>
          <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
        </div>

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={!canSubmit || flowState === 'submitting'}
          className={`w-full py-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-all ${
            canSubmit && flowState !== 'submitting'
              ? 'bg-ub-red text-white hover:opacity-90 shadow-sm'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
          }`}
        >
          {flowState === 'submitting' ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Submitting & Starting AI Analysis…
            </>
          ) : (
            <>
              <Send size={16} />
              Submit &amp; Run AI Analysis
            </>
          )}
        </button>
      </div>

      {/* Info box */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
        <p className="text-xs font-semibold text-ub-blue mb-2">What happens after you submit?</p>
        <div className="space-y-1.5">
          {[
            'Complaint is registered instantly with a unique ID',
            'AI checks for sensitive information and protects customer privacy',
            'Multiple AI agents classify, analyse sentiment, and check compliance',
            'A draft response is generated automatically',
            'Complaint is routed — auto-sent or sent to you for review',
          ].map((step, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-gray-600">
              <span className="w-4 h-4 rounded-full bg-ub-blue text-white flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                {i + 1}
              </span>
              {step}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

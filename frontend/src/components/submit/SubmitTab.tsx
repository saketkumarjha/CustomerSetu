import { useState, useRef, useCallback } from 'react'
import {
  Send, Upload, X, FileImage, CheckCircle2, AlertCircle,
  ChevronRight, Loader2, Zap,
} from 'lucide-react'
import { api } from '../../lib/api'
import type { TabId } from '../../types'

const CHANNELS = ['Email', 'Phone', 'Web Form', 'Mobile App', 'Social Media']
const AUTO_MODE_KEY = 'auto_resolution_enabled'

interface Props {
  setActive: (id: TabId) => void
}

// 'pending'     → submitted, waiting for staff to manually run the pipeline
// 'auto_queued' → submitted + pipeline silently fired (Auto Resolution ON)
type FlowState = 'form' | 'submitting' | 'pending' | 'auto_queued' | 'error'

export function SubmitTab({ setActive }: Props) {
  const [complaintText, setComplaintText] = useState('')
  const [channel, setChannel] = useState('Email')
  const [customerId, setCustomerId] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const [flowState, setFlowState] = useState<FlowState>('form')
  const [complaintId, setComplaintId] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

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

  const handleSubmit = async () => {
    if (!canSubmit) return
    setFlowState('submitting')
    setErrorMsg(null)

    const idempotencyKey = crypto.randomUUID()
    const form = new FormData()
    form.append('complaint_text', complaintText.trim())
    form.append('channel', channel)
    form.append('customer_id', customerId.trim())
    if (imageFile) form.append('image', imageFile)

    try {
      const res = await api.complaints.submit(form, idempotencyKey)
      setComplaintId(res.complaint_id)

      const autoMode = localStorage.getItem(AUTO_MODE_KEY) === 'true'
      if (autoMode) {
        // Fire-and-forget: run pipeline silently in backend, no SSE visualization
        api.pipeline.run(res.complaint_id).catch(console.error)
        setFlowState('auto_queued')
      } else {
        setFlowState('pending')
      }
    } catch (e) {
      setFlowState('error')
      setErrorMsg(e instanceof Error ? e.message : 'Something went wrong. Please try again.')
    }
  }

  const reset = () => {
    setFlowState('form')
    setComplaintText('')
    setChannel('Email')
    setCustomerId('')
    setImageFile(null)
    setComplaintId(null)
    setErrorMsg(null)
  }

  if (flowState === 'error') {
    return (
      <div className="max-w-xl mx-auto mt-12 text-center">
        <div className="bg-red-50 border border-red-200 rounded-2xl p-8">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-red-800 mb-2">Something went wrong</h2>
          <p className="text-sm text-red-600 mb-6">{errorMsg}</p>
          <button onClick={reset} className="px-6 py-2.5 rounded-md bg-ub-blue text-white text-sm font-semibold hover:opacity-90">
            Try Again
          </button>
        </div>
      </div>
    )
  }

  // ── Pending: submitted, waiting for manual pipeline run ───────────────────
  if (flowState === 'pending') {
    return (
      <div className="max-w-xl mx-auto mt-12">
        <div className="bg-white border border-green-200 rounded-2xl p-8 text-center shadow-sm">
          <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-gray-800 mb-1">Complaint Registered</h2>
          <p className="text-sm font-mono text-gray-500 mb-3">{complaintId}</p>
          <p className="text-sm text-gray-600 mb-6 leading-relaxed">
            The complaint is saved and waiting in <strong>Pending Analysis</strong>.
            Open the AI Analysis tab, select it, and click <strong>Run AI Analysis</strong> when ready.
          </p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => setActive('pipeline' as TabId)}
              className="flex items-center gap-1.5 px-5 py-2.5 rounded-md bg-ub-blue text-white text-sm font-semibold hover:opacity-90"
            >
              Go to AI Analysis <ChevronRight size={14} />
            </button>
            <button
              onClick={reset}
              className="px-4 py-2.5 rounded-md border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
            >
              Submit New
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Auto-queued: submitted + pipeline silently running ────────────────────
  if (flowState === 'auto_queued') {
    return (
      <div className="max-w-xl mx-auto mt-12">
        <div className="bg-white border border-green-200 rounded-2xl p-8 text-center shadow-sm">
          <div className="flex items-center justify-center gap-2 mb-4">
            <CheckCircle2 className="w-10 h-10 text-green-500" />
            <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
              <Zap size={16} className="text-green-700" />
            </div>
          </div>
          <h2 className="text-lg font-bold text-gray-800 mb-1">Complaint Registered</h2>
          <p className="text-sm font-mono text-gray-500 mb-3">{complaintId}</p>
          <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 mb-6 text-left">
            <p className="text-xs font-semibold text-green-700 mb-0.5 flex items-center gap-1.5">
              <Zap size={11} /> Auto Resolution is ON
            </p>
            <p className="text-xs text-green-700 leading-relaxed">
              The AI pipeline is running silently in the background. Results will appear in the Complaints tab once complete.
            </p>
          </div>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => setActive('complaints' as TabId)}
              className="flex items-center gap-1.5 px-5 py-2.5 rounded-md bg-ub-blue text-white text-sm font-semibold hover:opacity-90"
            >
              View Complaints <ChevronRight size={14} />
            </button>
            <button
              onClick={reset}
              className="px-4 py-2.5 rounded-md border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
            >
              Submit New
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {/* Page header */}
      <div className="rounded-2xl p-5 text-white bg-ub-blue border border-white/10 shadow-glass">
        <h1 className="text-lg font-bold mb-1">Register New Complaint</h1>
        <p className="text-blue-200 text-sm">
          Fill in the customer details below. The complaint is saved first; run the AI pipeline from the Analysis tab, or enable Auto Resolution for hands-free processing.
        </p>
      </div>

      {/* Form */}
      <div className="glass-panel p-5 space-y-4">
        {/* Customer ID */}
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">
            Customer ID <span className="text-red-500">*</span>
          </label>
          <input
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            placeholder="e.g. CUST-00123 or phone number"
            className="w-full border border-gray-200 rounded-md px-3 py-2.5 text-sm focus:outline-none focus:border-ub-blue"
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
                className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-all ${
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
            className="w-full border border-gray-200 rounded-md px-3 py-2.5 text-sm focus:outline-none focus:border-ub-blue resize-none leading-relaxed"
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
          className={`w-full py-3 rounded-md text-sm font-bold flex items-center justify-center gap-2 transition-all ${
            canSubmit && flowState !== 'submitting'
              ? 'bg-ub-red text-white hover:opacity-90 shadow-sm'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
          }`}
        >
          {flowState === 'submitting' ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Submitting…
            </>
          ) : (
            <>
              <Send size={16} />
              Submit Complaint
            </>
          )}
        </button>
      </div>

      {/* Info box */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
        <p className="text-xs font-semibold text-ub-blue mb-2">What happens after you submit?</p>
        <div className="space-y-1.5">
          {[
            'Complaint is registered instantly with a unique ID and saved as Pending',
            'It appears in the AI Analysis tab under "Pending Analysis"',
            'A staff member selects it and clicks Run AI Analysis — or enable Auto Resolution for hands-free processing',
            'AI checks PII, classifies, analyses sentiment, checks RBI compliance, and generates a draft',
            'Complaint is routed — auto-sent if confidence is high, or queued for officer review',
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

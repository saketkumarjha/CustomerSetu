/**
 * Pipeline SSE helpers — logs + handles unnamed `message` events
 * (some proxies strip the SSE `event:` field).
 */

import type { PipelineSSEEvent } from '../types'

export interface PipelineSseCallbacks {
  onAgentUpdate: (event: PipelineSSEEvent) => void
  onPipelineComplete: (payload: Record<string, unknown>) => void
  onPipelineError: (payload: { error?: string }) => void
  onConnected?: () => void
  onStreamClosed?: () => void
  /** Browser-level disconnect (wrong URL, 401, server stopped, etc.) */
  onTransportError?: () => void
  /** Append-only debug lines for the UI */
  onLog?: (line: string) => void
}

function sseLog(onLog: PipelineSseCallbacks['onLog'], msg: string, extra?: unknown) {
  const suffix =
    extra === undefined ? '' : typeof extra === 'string' ? ` ${extra}` : ` ${JSON.stringify(extra)}`
  const line = `[${new Date().toISOString().slice(11, 19)}] ${msg}${suffix}`
  console.info('[Pipeline SSE]', msg, extra ?? '')
  onLog?.(line)
}

function normalizeAgentPayload(raw: Record<string, unknown>): PipelineSSEEvent | null {
  const agent = raw.agent as string | undefined
  const order = (raw.order ?? raw.agent_order) as number | undefined
  if (!agent || order == null) return null
  const st = String(raw.status ?? '').toLowerCase()
  let status: PipelineSSEEvent['status']
  if (st === 'processing') status = 'processing'
  else if (st === 'complete') status = 'complete'
  else if (st === 'failed') status = 'failed'
  else status = undefined
  return {
    event: 'agent_update',
    agent,
    order,
    status,
    decision: raw.decision as string | undefined,
    confidence: typeof raw.confidence === 'number' ? raw.confidence : undefined,
    reasoning: raw.reasoning as string | undefined,
    evidence: raw.evidence as string[] | undefined,
    duration_ms: raw.duration_ms as number | undefined,
  }
}

/** Route a parsed JSON object from any SSE channel */
export function dispatchPipelineSseData(
  raw: Record<string, unknown>,
  cbs: PipelineSseCallbacks,
  onLog?: PipelineSseCallbacks['onLog'],
): void {
  const evt = raw.event as string | undefined

  // Pipeline-level completion (JSON body has no `event` field — only SSE wire `event:` line)
  const isPipelineDone =
    evt === 'pipeline_complete' ||
    (raw.status === 'complete' &&
      typeof raw.complaint_id === 'string' &&
      raw.agent === undefined &&
      raw.order === undefined)

  if (isPipelineDone) {
    sseLog(onLog, 'pipeline_complete', raw)
    cbs.onPipelineComplete(raw)
    return
  }

  const isPipelineErr =
    evt === 'pipeline_error' ||
    (typeof raw.error === 'string' &&
      typeof raw.complaint_id === 'string' &&
      raw.agent === undefined)

  if (isPipelineErr) {
    sseLog(onLog, 'pipeline_error', raw)
    cbs.onPipelineError({ error: raw.error as string })
    return
  }

  const agentEvt = normalizeAgentPayload(raw)
  if (agentEvt) {
    sseLog(onLog, `agent_update ${agentEvt.agent}`, { status: agentEvt.status, order: agentEvt.order })
    cbs.onAgentUpdate(agentEvt)
    return
  }

  // Known informational events — log them but no UI action needed.
  if (evt === 'escalation_triggered' || evt === 'assigned_to_agent' || evt === 'response_sent') {
    sseLog(onLog, `event: ${evt}`, raw)
    return
  }

  sseLog(onLog, 'unhandled SSE payload', raw)
}

/**
 * Attach all listeners. Call after `new EventSource(...)`.
 * Returns a cleanup function that removes listeners (does not close ES).
 */
export function attachPipelineEventSource(es: EventSource, cbs: PipelineSseCallbacks): () => void {
  const onLog = cbs.onLog

  const onConnected = (e: MessageEvent) => {
    sseLog(onLog, 'event: connected', e.data)
    cbs.onConnected?.()
  }
  const onAgentUpdate = (e: MessageEvent) => {
    try {
      const raw = JSON.parse(e.data) as Record<string, unknown>
      dispatchPipelineSseData(raw, cbs, onLog)
    } catch (err) {
      sseLog(onLog, 'agent_update JSON parse failed', String(err))
    }
  }
  const onPipelineComplete = (e: MessageEvent) => {
    try {
      const raw = JSON.parse(e.data) as Record<string, unknown>
      sseLog(onLog, 'event: pipeline_complete', raw)
      cbs.onPipelineComplete(raw)
    } catch (err) {
      sseLog(onLog, 'pipeline_complete parse failed', String(err))
    }
  }
  const onPipelineError = (e: MessageEvent) => {
    try {
      const raw = JSON.parse(e.data) as Record<string, unknown>
      sseLog(onLog, 'event: pipeline_error', raw)
      cbs.onPipelineError({ error: raw.error as string })
    } catch {
      cbs.onPipelineError({ error: e.data })
    }
  }
  const onStreamClosed = (e: MessageEvent) => {
    sseLog(onLog, 'event: stream_closed', e.data)
    cbs.onStreamClosed?.()
  }

  /** Proxies sometimes deliver everything as default `message` */
  const onMessage = (e: MessageEvent) => {
    try {
      const raw = JSON.parse(e.data) as Record<string, unknown>
      sseLog(onLog, 'event: message (fallback)', raw)
      dispatchPipelineSseData(raw, cbs, onLog)
    } catch (err) {
      sseLog(onLog, 'message JSON parse failed', String(err))
    }
  }

  es.addEventListener('connected', onConnected)
  es.addEventListener('agent_update', onAgentUpdate)
  es.addEventListener('pipeline_complete', onPipelineComplete)
  es.addEventListener('pipeline_error', onPipelineError)
  es.addEventListener('stream_closed', onStreamClosed)
  es.addEventListener('message', onMessage)

  es.onerror = () => {
    sseLog(onLog, 'EventSource onerror (connection lost, wrong URL, or 401 — check Network tab)')
    cbs.onTransportError?.()
  }

  return () => {
    es.onerror = null
    es.removeEventListener('connected', onConnected)
    es.removeEventListener('agent_update', onAgentUpdate)
    es.removeEventListener('pipeline_complete', onPipelineComplete)
    es.removeEventListener('pipeline_error', onPipelineError)
    es.removeEventListener('stream_closed', onStreamClosed)
    es.removeEventListener('message', onMessage)
  }
}

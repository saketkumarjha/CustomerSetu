import { useState, useCallback, useRef } from 'react'
import {
  LayoutDashboard, List, Clock4, BarChart2, Upload, Settings2,
  RefreshCw, Plus, Search, ChevronDown, ChevronUp, Check, X,
  Download, AlertTriangle, CheckCircle2, Trash2, Edit2, Eye,
  BookOpen, Layers, Shield, Zap,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { api } from '../../lib/api'
import type {
  KBEntry, KBQueueEntry, KBReference, KBMetrics,
  KBEntriesResponse, KBAnalytics, KBBulkValidateResult, KBEntryPayload,
} from '../../lib/api'
import { useApiData } from '../../hooks/useApiData'

// ── Helpers ────────────────────────────────────────────────────────────────────

type SubTab = 'overview' | 'entries' | 'queue' | 'analytics' | 'import' | 'jobs'

const TIER_COLORS: Record<number, string> = {
  0: 'bg-slate-100 text-slate-600 border-slate-200',
  1: 'bg-blue-50 text-blue-700 border-blue-200',
  2: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  3: 'bg-violet-50 text-violet-700 border-violet-200',
  4: 'bg-purple-50 text-purple-700 border-purple-200',
  5: 'bg-red-50 text-red-700 border-red-200',
}

const QUALITY_COLOR = (q: number) => {
  if (q >= 0.8) return 'text-emerald-600'
  if (q >= 0.6) return 'text-amber-600'
  return 'text-red-500'
}

const QUALITY_BAR = (q: number) => {
  if (q >= 0.8) return 'bg-emerald-500'
  if (q >= 0.6) return 'bg-amber-400'
  return 'bg-red-400'
}

function TierBadge({ level, label }: { level: number; label?: string }) {
  const cls = TIER_COLORS[level] ?? TIER_COLORS[0]
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] font-semibold ${cls}`}>
      T{level}{label ? ` · ${label}` : ''}
    </span>
  )
}

function QualityBar({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${QUALITY_BAR(score)}`} style={{ width: `${score * 100}%` }} />
      </div>
      <span className={`text-xs font-semibold ${QUALITY_COLOR(score)}`}>{(score * 100).toFixed(0)}%</span>
    </div>
  )
}

function KpiCard({ label, value, sub, color = 'blue' }: {
  label: string; value: string | number; sub?: string; color?: 'blue' | 'emerald' | 'amber' | 'red'
}) {
  const ring = { blue: 'border-ub-blue/20 bg-ub-blue-light/60', emerald: 'border-emerald-200 bg-emerald-50/60', amber: 'border-amber-200 bg-amber-50/60', red: 'border-red-200 bg-red-50/60' }[color]
  const val = { blue: 'text-ub-blue', emerald: 'text-emerald-700', amber: 'text-amber-700', red: 'text-red-600' }[color]
  return (
    <div className={`glass-panel p-4 border ${ring}`}>
      <p className="text-xs text-slate-500 font-medium mb-1">{label}</p>
      <p className={`text-2xl font-bold ${val}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}

// ── Entry Modal ────────────────────────────────────────────────────────────────

interface EntryModalProps {
  entry?: KBEntry
  reference: KBReference | null
  onClose: () => void
  onSaved: () => void
}

function EntryModal({ entry, reference, onClose, onSaved }: EntryModalProps) {
  const isEdit = !!entry
  const [form, setForm] = useState<KBEntryPayload>({
    tier_level: entry?.tier_level ?? 0,
    tier_scope: entry?.tier_scope ?? '',
    category: entry?.category ?? (reference?.categories[0] ?? ''),
    issue_type: entry?.issue_type ?? '',
    resolution_text: entry?.resolution_text ?? '',
    quality_score: entry?.quality_score ?? 0.8,
    verified: entry?.verified ?? false,
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const tierLabels = reference?.tier_labels ?? {}

  async function handleSave() {
    if (!form.category || !form.issue_type || form.resolution_text.length < 50) {
      setErr('Category, issue type, and resolution text (≥50 chars) are required.')
      return
    }
    setSaving(true)
    setErr('')
    try {
      if (isEdit && entry) {
        await api.kb.updateEntry(entry.id, form)
      } else {
        await api.kb.createEntry(form)
      }
      onSaved()
      onClose()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const scopeHint = reference?.tier_scope_formats[String(form.tier_level)]
  const field = 'w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ub-blue/30 bg-white'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto animate-slide-up">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-800">{isEdit ? 'Edit KB Entry' : 'Create KB Entry'}</h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400"><X size={16} /></button>
        </div>
        <div className="px-6 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">Tier Level</label>
              <select className={field} value={form.tier_level} onChange={e => setForm(f => ({ ...f, tier_level: Number(e.target.value), tier_scope: '' }))}>
                {Object.entries(tierLabels).map(([k, v]) => <option key={k} value={k}>T{k} — {v}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">
                Tier Scope {scopeHint && <span className="text-slate-300">({scopeHint})</span>}
              </label>
              <input className={field} value={form.tier_scope} placeholder={scopeHint ?? 'N/A'} disabled={!scopeHint}
                onChange={e => setForm(f => ({ ...f, tier_scope: e.target.value }))} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">Category</label>
              <select className={field} value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}>
                {(reference?.categories ?? []).map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">Issue Type</label>
              <input className={field} value={form.issue_type} placeholder="e.g. Failed transaction" onChange={e => setForm(f => ({ ...f, issue_type: e.target.value }))} />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Resolution Text <span className="text-slate-300">(min 50 chars)</span></label>
            <textarea className={`${field} h-28 resize-none`} value={form.resolution_text} onChange={e => setForm(f => ({ ...f, resolution_text: e.target.value }))} placeholder="Detailed resolution steps..." />
            <p className="text-xs text-slate-300 mt-1 text-right">{form.resolution_text.length} chars</p>
          </div>
          <div className="grid grid-cols-2 gap-3 items-end">
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">Quality Score ({(form.quality_score * 100).toFixed(0)}%)</label>
              <input type="range" min={0.1} max={1} step={0.01} value={form.quality_score}
                onChange={e => setForm(f => ({ ...f, quality_score: Number(e.target.value) }))}
                className="w-full accent-ub-blue" />
            </div>
            <label className="flex items-center gap-2 cursor-pointer pb-1">
              <input type="checkbox" checked={form.verified} onChange={e => setForm(f => ({ ...f, verified: e.target.checked }))}
                className="w-4 h-4 rounded accent-ub-blue" />
              <span className="text-sm text-slate-600">Mark as Verified</span>
            </label>
          </div>
          {err && <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{err}</p>}
        </div>
        <div className="px-6 py-4 border-t border-slate-100 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">Cancel</button>
          <button onClick={handleSave} disabled={saving}
            className="px-5 py-2 text-sm bg-ub-blue text-white rounded-lg hover:bg-ub-blue-dark transition-colors font-medium disabled:opacity-50">
            {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Entry'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Overview Sub-tab ───────────────────────────────────────────────────────────

function OverviewSection({ metrics, refData }: { metrics: KBMetrics | null; refData: KBReference | null }) {
  if (!metrics) return (
    <div className="glass-panel p-8 flex items-center justify-center text-slate-400 text-sm">
      No metrics data available — backend may be offline.
    </div>
  )

  const tierLabels = refData?.tier_labels ?? {}

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="Total Entries" value={metrics.total} sub="in knowledge base" color="blue" />
        <KpiCard label="Verified" value={metrics.verified} sub={`${metrics.total ? ((metrics.verified / metrics.total) * 100).toFixed(0) : 0}% of total`} color="emerald" />
        <KpiCard label="Pending Review" value={metrics.pending} sub="unverified entries" color="amber" />
        <KpiCard label="Avg Quality" value={`${(metrics.avg_quality * 100).toFixed(0)}%`} sub="across all entries" color={metrics.avg_quality >= 0.75 ? 'emerald' : 'amber'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Tier distribution */}
        <div className="glass-panel p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2"><Layers size={14} className="text-ub-blue" />Tier Distribution</h3>
          <div className="space-y-3">
            {metrics.tier_distribution.map(t => {
              const pct = metrics.total ? (t.count / metrics.total) * 100 : 0
              return (
                <div key={t.tier_level}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-slate-600 font-medium">T{t.tier_level} · {tierLabels[String(t.tier_level)] ?? t.label}</span>
                    <span className="text-xs font-bold text-slate-700">{t.count}</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-ub-blue rounded-full transition-all" style={{ width: `${pct}%`, opacity: 0.4 + t.tier_level * 0.12 }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Coverage gaps */}
        <div className="glass-panel p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2"><AlertTriangle size={14} className="text-amber-500" />Coverage Gaps</h3>
          {metrics.coverage_gaps.length === 0 ? (
            <div className="flex items-center gap-2 text-emerald-600 text-sm py-4"><CheckCircle2 size={16} />All categories have sufficient coverage.</div>
          ) : (
            <div className="space-y-2">
              {metrics.coverage_gaps.slice(0, 8).map(g => (
                <div key={g.category} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0">
                  <span className="text-xs text-slate-600">{g.category}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-400">{g.count} / {g.needed} needed</span>
                    <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-amber-400 rounded-full" style={{ width: `${Math.min((g.count / g.needed) * 100, 100)}%` }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent additions */}
      <div className="glass-panel p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2"><BookOpen size={14} className="text-ub-blue" />Recent Additions</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-100">
                {['ID', 'Tier', 'Category', 'Issue Type', 'Quality', 'Verified', 'Source'].map(h => (
                  <th key={h} className="text-left pb-2 pr-4 text-slate-400 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.recent_additions.map(e => (
                <tr key={e.id} className="border-b border-slate-50 hover:bg-slate-50/60 transition-colors">
                  <td className="py-2 pr-4 font-mono text-slate-500">#{e.id}</td>
                  <td className="py-2 pr-4"><TierBadge level={e.tier_level} /></td>
                  <td className="py-2 pr-4 text-slate-600">{e.category}</td>
                  <td className="py-2 pr-4 text-slate-600 max-w-[140px] truncate">{e.issue_type}</td>
                  <td className="py-2 pr-4 w-24"><QualityBar score={e.quality_score} /></td>
                  <td className="py-2 pr-4">
                    {e.verified
                      ? <CheckCircle2 size={14} className="text-emerald-500" />
                      : <Clock4 size={14} className="text-amber-400" />}
                  </td>
                  <td className="py-2 text-slate-400 capitalize">{e.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── Entries Sub-tab ────────────────────────────────────────────────────────────

function EntriesSection({ refData }: { refData: KBReference | null }) {
  const [search, setSearch] = useState('')
  const [filterCat, setFilterCat] = useState('')
  const [filterTier, setFilterTier] = useState<string>('')
  const [filterVerified, setFilterVerified] = useState<string>('')
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState<{ mode: 'create' | 'edit' | 'view'; entry?: KBEntry } | null>(null)
  const [deleting, setDeleting] = useState<number | null>(null)
  const [tick, setTick] = useState(0)

  const tierLabels = refData?.tier_labels ?? {}

  const params = {
    search: search || undefined,
    category: filterCat || undefined,
    tier_level: filterTier !== '' ? Number(filterTier) : undefined,
    verified: filterVerified !== '' ? filterVerified === 'true' : undefined,
    page,
    page_size: 15,
  }

  const { data, loading } = useApiData<KBEntriesResponse>(
    () => api.kb.entries(params),
    [search, filterCat, filterTier, filterVerified, page, tick],
  )

  const reload = () => { setTick(t => t + 1) }

  async function handleDelete(id: number) {
    if (!confirm('Delete this KB entry? This cannot be undone.')) return
    setDeleting(id)
    try { await api.kb.deleteEntry(id); reload() }
    catch { alert('Delete failed') }
    finally { setDeleting(null) }
  }

  const select = 'text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-ub-blue/30'

  return (
    <div className="space-y-4">
      {modal && (
        <EntryModal
          entry={modal.entry}
          reference={refData}
          onClose={() => setModal(null)}
          onSaved={reload}
        />
      )}

      {/* Filter bar */}
      <div className="glass-panel p-3 flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[160px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="w-full pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-ub-blue/30"
            placeholder="Search entries…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
          />
        </div>
        <select className={select} value={filterCat} onChange={e => { setFilterCat(e.target.value); setPage(1) }}>
          <option value="">All Categories</option>
          {(refData?.categories ?? []).map(c => <option key={c}>{c}</option>)}
        </select>
        <select className={select} value={filterTier} onChange={e => { setFilterTier(e.target.value); setPage(1) }}>
          <option value="">All Tiers</option>
          {Object.entries(tierLabels).map(([k, v]) => <option key={k} value={k}>T{k} · {v}</option>)}
        </select>
        <select className={select} value={filterVerified} onChange={e => { setFilterVerified(e.target.value); setPage(1) }}>
          <option value="">All Status</option>
          <option value="true">Verified</option>
          <option value="false">Pending</option>
        </select>
        <button onClick={() => setModal({ mode: 'create' })}
          className="flex items-center gap-1.5 px-4 py-2 bg-ub-blue text-white text-sm font-medium rounded-lg hover:bg-ub-blue-dark transition-colors ml-auto">
          <Plus size={14} />New Entry
        </button>
      </div>

      {/* Table */}
      <div className="glass-panel overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-slate-400 text-sm">Loading entries…</div>
        ) : !data || data.entries.length === 0 ? (
          <div className="p-10 text-center text-slate-400 text-sm">No entries match your filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50/80 border-b border-slate-100">
                <tr>
                  {['ID', 'Tier', 'Category', 'Issue Type', 'Quality', 'Verified', 'Usage', 'Source', ''].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-slate-400 font-semibold uppercase tracking-wide text-[10px]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.entries.map(e => (
                  <tr key={e.id} className="border-b border-slate-50 hover:bg-slate-50/60 transition-colors">
                    <td className="px-4 py-2.5 font-mono text-slate-500">#{e.id}</td>
                    <td className="px-4 py-2.5"><TierBadge level={e.tier_level} /></td>
                    <td className="px-4 py-2.5 text-slate-600 font-medium">{e.category}</td>
                    <td className="px-4 py-2.5 text-slate-600 max-w-[160px] truncate">{e.issue_type}</td>
                    <td className="px-4 py-2.5 w-28"><QualityBar score={e.quality_score} /></td>
                    <td className="px-4 py-2.5">
                      {e.verified
                        ? <span className="inline-flex items-center gap-1 text-emerald-600 font-medium"><CheckCircle2 size={12} />Yes</span>
                        : <span className="inline-flex items-center gap-1 text-amber-500 font-medium"><Clock4 size={12} />Pending</span>}
                    </td>
                    <td className="px-4 py-2.5 text-slate-500">{e.usage_count}</td>
                    <td className="px-4 py-2.5 text-slate-400 capitalize">{e.source}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-1">
                        <button title="View" onClick={() => setModal({ mode: 'view', entry: e })}
                          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-slate-100 text-slate-400"><Eye size={13} /></button>
                        <button title="Edit" onClick={() => setModal({ mode: 'edit', entry: e })}
                          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-ub-blue-light text-ub-blue"><Edit2 size={13} /></button>
                        <button title="Delete" onClick={() => handleDelete(e.id)} disabled={deleting === e.id}
                          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-red-50 text-red-400 disabled:opacity-40"><Trash2 size={13} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 bg-slate-50/50">
            <span className="text-xs text-slate-400">
              Showing {(page - 1) * 15 + 1}–{Math.min(page * 15, data.total)} of {data.total} entries
            </span>
            <div className="flex items-center gap-1">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                className="px-3 py-1.5 text-xs rounded-md border border-slate-200 hover:bg-slate-100 disabled:opacity-40">Prev</button>
              {Array.from({ length: Math.min(data.total_pages, 5) }, (_, i) => {
                const p = i + 1
                return (
                  <button key={p} onClick={() => setPage(p)}
                    className={`w-8 h-7 text-xs rounded-md border transition-colors ${page === p ? 'bg-ub-blue text-white border-ub-blue' : 'border-slate-200 hover:bg-slate-100'}`}>
                    {p}
                  </button>
                )
              })}
              <button disabled={page === data.total_pages} onClick={() => setPage(p => p + 1)}
                className="px-3 py-1.5 text-xs rounded-md border border-slate-200 hover:bg-slate-100 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>

      {/* View modal (read-only) */}
      {modal?.mode === 'view' && modal.entry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto animate-slide-up">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h2 className="text-base font-semibold text-slate-800">KB Entry #{modal.entry.id}</h2>
              <button onClick={() => setModal(null)} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400"><X size={16} /></button>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><p className="text-xs text-slate-400 mb-1">Tier</p><TierBadge level={modal.entry.tier_level} label={tierLabels[String(modal.entry.tier_level)]} /></div>
                <div><p className="text-xs text-slate-400 mb-1">Scope</p><p className="font-mono text-slate-600 text-xs">{modal.entry.tier_scope || '—'}</p></div>
                <div><p className="text-xs text-slate-400 mb-1">Category</p><p className="text-slate-700">{modal.entry.category}</p></div>
                <div><p className="text-xs text-slate-400 mb-1">Issue Type</p><p className="text-slate-700">{modal.entry.issue_type}</p></div>
                <div><p className="text-xs text-slate-400 mb-1">Quality</p><QualityBar score={modal.entry.quality_score} /></div>
                <div><p className="text-xs text-slate-400 mb-1">Usage</p><p className="text-slate-700">{modal.entry.usage_count} times</p></div>
              </div>
              <div>
                <p className="text-xs text-slate-400 mb-2">Resolution Text</p>
                <p className="text-sm text-slate-700 bg-slate-50 rounded-xl p-4 leading-relaxed">{modal.entry.resolution_text}</p>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Created: {new Date(modal.entry.created_at).toLocaleDateString()}</span>
                <span>Updated: {new Date(modal.entry.updated_at).toLocaleDateString()}</span>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-slate-100 flex justify-end gap-3">
              <button onClick={() => setModal({ mode: 'edit', entry: modal.entry })}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-ub-blue text-white rounded-lg hover:bg-ub-blue-dark transition-colors"><Edit2 size={13} />Edit</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )

}

// ── Queue Sub-tab ──────────────────────────────────────────────────────────────

function QueueSection({ refData }: { refData: KBReference | null }) {
  const [tick, setTick] = useState(0)
  const { data: queue, loading } = useApiData<KBQueueEntry[]>(() => api.kb.queue(), [tick])
  const [acting, setActing] = useState<number | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [bulkLoading, setBulkLoading] = useState(false)
  const [feedback, setFeedback] = useState('')
  const reload = () => { setTick(t => t + 1); setFeedback('') }

  const pending = (queue ?? []).filter(q => !q.added_to_kb && !q.rejection_reason)
  const tierLabels = refData?.tier_labels ?? {}

  async function handleApprove(q: KBQueueEntry) {
    setActing(q.id)
    try {
      await api.kb.approveQueue(q.id, {
        category: q.category, issue_type: q.issue_type, resolution_text: q.resolution_text,
        quality_score: q.recommended_quality_score, tier_level: q.tier_level,
        tier_scope: q.tier_scope, verified: true,
      })
      reload()
    } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Approve failed') }
    finally { setActing(null) }
  }

  async function handleReject(q: KBQueueEntry) {
    const reason = prompt('Rejection reason:')
    if (!reason) return
    setActing(q.id)
    try { await api.kb.rejectQueue(q.id, reason); reload() }
    catch { alert('Reject failed') }
    finally { setActing(null) }
  }

  async function handleBulkApprove() {
    setBulkLoading(true)
    try {
      await api.kb.bulkApprove({ min_quality_score: 0.75 })
      setFeedback('Bulk approve complete.')
      reload()
    } catch (e: unknown) { setFeedback(e instanceof Error ? e.message : 'Bulk approve failed') }
    finally { setBulkLoading(false) }
  }

  async function handleBulkReject() {
    if (!confirm('Reject ALL pending queue entries?')) return
    setBulkLoading(true)
    try {
      await api.kb.bulkReject('Bulk rejected by admin')
      setFeedback('All pending entries rejected.')
      reload()
    } catch (e: unknown) { setFeedback(e instanceof Error ? e.message : 'Bulk reject failed') }
    finally { setBulkLoading(false) }
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="glass-panel p-3 flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-600">Pending Review:</span>
          <span className="px-2.5 py-0.5 bg-amber-50 text-amber-700 rounded-full text-sm font-bold border border-amber-200">{pending.length}</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {feedback && <span className="text-xs text-emerald-600 font-medium">{feedback}</span>}
          <button onClick={handleBulkApprove} disabled={bulkLoading || pending.length === 0}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-40 font-medium">
            <Check size={14} />Bulk Approve ≥75%
          </button>
          <button onClick={handleBulkReject} disabled={bulkLoading || pending.length === 0}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-ub-red text-white rounded-lg hover:opacity-90 transition-colors disabled:opacity-40 font-medium">
            <X size={14} />Bulk Reject
          </button>
        </div>
      </div>

      {loading ? (
        <div className="glass-panel p-10 text-center text-slate-400 text-sm">Loading queue…</div>
      ) : pending.length === 0 ? (
        <div className="glass-panel p-10 flex flex-col items-center gap-3 text-slate-400">
          <CheckCircle2 size={32} className="text-emerald-400" />
          <p className="text-sm font-medium">Queue is clear — no pending entries.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {pending.map(q => {
            const isOpen = expanded === q.id
            return (
              <div key={q.id} className="glass-panel overflow-hidden transition-all">
                <div className="p-4 flex items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      <TierBadge level={q.tier_level} label={tierLabels[String(q.tier_level)]} />
                      <span className="text-xs bg-ub-blue-light text-ub-blue px-2 py-0.5 rounded-full font-medium border border-ub-blue/20">{q.category}</span>
                      <span className="text-xs text-slate-400 font-mono">#{q.id} · {q.complaint_id}</span>
                    </div>
                    <p className="text-sm font-medium text-slate-700 mb-1">{q.issue_type}</p>
                    <p className="text-xs text-slate-500 line-clamp-2">{q.resolution_text}</p>

                    <div className="flex items-center gap-4 mt-3">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-slate-400">Confidence</span>
                        <div className="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full bg-ub-blue rounded-full" style={{ width: `${(q.confidence_score ?? 0) * 100}%` }} />
                        </div>
                        <span className="text-xs font-semibold text-ub-blue">{((q.confidence_score ?? 0) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-slate-400">Quality</span>
                        <span className={`text-xs font-bold ${QUALITY_COLOR(q.recommended_quality_score ?? 0)}`}>
                          {((q.recommended_quality_score ?? 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-2 flex-shrink-0">
                    <div className="flex items-center gap-2">
                      <button onClick={() => handleApprove(q)} disabled={acting === q.id}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors font-medium disabled:opacity-40">
                        <Check size={12} />Approve
                      </button>
                      <button onClick={() => handleReject(q)} disabled={acting === q.id}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-ub-red text-white rounded-lg hover:opacity-90 transition-colors font-medium disabled:opacity-40">
                        <X size={12} />Reject
                      </button>
                    </div>
                    <button onClick={() => setExpanded(isOpen ? null : q.id)}
                      className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600">
                      {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      {isOpen ? 'Less' : 'Details'}
                    </button>
                  </div>
                </div>

                {isOpen && (
                  <div className="px-4 pb-4 border-t border-slate-50 pt-3 space-y-3">
                    <p className="text-sm text-slate-600 bg-slate-50 rounded-xl p-3 leading-relaxed">{q.resolution_text}</p>
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-500">
                      <div><span className="text-slate-400">Action: </span>{q.agent_action || '—'}</div>
                      <div><span className="text-slate-400">Resolution type: </span>{q.resolution_type || '—'}</div>
                      <div><span className="text-slate-400">Feedback score: </span>{q.customer_feedback_score ?? '—'}</div>
                      <div><span className="text-slate-400">Scheduled: </span>{q.scheduled_for ? new Date(q.scheduled_for).toLocaleDateString() : '—'}</div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Analytics Sub-tab ──────────────────────────────────────────────────────────

const CHART_COLORS = ['#003087', '#1d4ed8', '#4f46e5', '#7c3aed', '#a21caf', '#be185d', '#b45309', '#047857']

function AnalyticsSection() {
  const { data: analytics, loading } = useApiData<KBAnalytics>(() => api.kb.analytics(), [])

  if (loading) return <div className="glass-panel p-10 text-center text-slate-400 text-sm">Loading analytics…</div>
  if (!analytics) return <div className="glass-panel p-10 text-center text-slate-400 text-sm">Analytics unavailable.</div>

  const topUsage = (analytics.top_entries_by_usage ?? []).slice(0, 8).map((r: Record<string, unknown>) => ({
    name: String(r.issue_type ?? r.category ?? `#${r.id}`).slice(0, 28),
    usage: Number(r.usage_count ?? 0),
    quality: Number(r.quality_score ?? 0),
  }))

  const catUsage = (analytics.category_usage ?? []).map((r: Record<string, unknown>) => ({
    name: String(r.category ?? '').slice(0, 14),
    count: Number(r.total_usage ?? r.count ?? 0),
  })).sort((a, b) => b.count - a.count).slice(0, 10)

  const qualDist = (analytics.quality_distribution ?? []).map((r: Record<string, unknown>) => ({
    name: String(r.bucket ?? r.range ?? r.label ?? ''),
    value: Number(r.count ?? 0),
  }))

  const tierQuality = (analytics.tier_quality ?? []).map((r: Record<string, unknown>) => ({
    name: `T${r.tier_level}`,
    quality: Math.round(Number(r.avg_quality ?? 0) * 100),
    count: Number(r.count ?? 0),
  }))

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top entries by usage */}
        <div className="glass-panel p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Top Entries by Usage</h3>
          {topUsage.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-6">No usage data yet.</p>
          ) : (
            <div className="space-y-2">
              {topUsage.map((e, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-xs text-slate-300 w-4 text-right">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-slate-600 truncate">{e.name}</p>
                    <div className="h-1.5 bg-slate-100 rounded-full mt-1 overflow-hidden">
                      <div className="h-full bg-ub-blue rounded-full" style={{ width: `${topUsage[0].usage ? (e.usage / topUsage[0].usage) * 100 : 0}%` }} />
                    </div>
                  </div>
                  <span className="text-xs font-bold text-slate-700 w-8 text-right">{e.usage}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Category usage bar chart */}
        <div className="glass-panel p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Category Usage</h3>
          {catUsage.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-6">No data.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={catUsage} layout="vertical" margin={{ left: 4, right: 12 }}>
                <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} width={80} />
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Bar dataKey="count" fill="#003087" radius={[0, 4, 4, 0]} maxBarSize={14} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Quality distribution */}
        <div className="glass-panel p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Quality Distribution</h3>
          {qualDist.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-6">No data.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={qualDist} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} innerRadius={40}>
                  {qualDist.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Tier quality */}
        <div className="glass-panel p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Avg Quality by Tier</h3>
          {tierQuality.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-6">No data.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={tierQuality} margin={{ left: 4, right: 12 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} unit="%" />
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e2e8f0' }} formatter={(v) => [`${v}%`, 'Avg Quality']} />
                <Bar dataKey="quality" fill="#003087" radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Category gaps table */}
      {analytics.category_gaps && analytics.category_gaps.length > 0 && (
        <div className="glass-panel p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2"><AlertTriangle size={14} className="text-amber-500" />Category Gaps</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-slate-100">
                <tr>
                  {['Category', 'Current Entries', 'Recommended', 'Coverage'].map(h => (
                    <th key={h} className="text-left pb-2 pr-4 text-slate-400 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {analytics.category_gaps.map((g: Record<string, unknown>, i) => {
                  const count = Number(g.count ?? 0), needed = Number(g.needed ?? g.recommended ?? 1)
                  const pct = Math.min((count / needed) * 100, 100)
                  return (
                    <tr key={i} className="border-b border-slate-50">
                      <td className="py-2 pr-4 text-slate-600 font-medium">{String(g.category ?? '—')}</td>
                      <td className="py-2 pr-4 text-slate-600">{count}</td>
                      <td className="py-2 pr-4 text-slate-400">{needed}</td>
                      <td className="py-2 pr-4 w-36">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${pct >= 100 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-400' : 'bg-red-400'}`} style={{ width: `${pct}%` }} />
                          </div>
                          <span className={`text-xs font-semibold ${pct >= 100 ? 'text-emerald-600' : pct >= 60 ? 'text-amber-600' : 'text-red-500'}`}>{pct.toFixed(0)}%</span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Import Sub-tab ─────────────────────────────────────────────────────────────

function ImportSection() {
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [validating, setValidating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [validateResult, setValidateResult] = useState<KBBulkValidateResult | null>(null)
  const [importResult, setImportResult] = useState<{ total_rows?: number; successful?: number; failed?: number } | null>(null)
  const [err, setErr] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  function handleDrop(ev: React.DragEvent) {
    ev.preventDefault()
    setDragging(false)
    const f = ev.dataTransfer.files[0]
    if (f) { setFile(f); setValidateResult(null); setImportResult(null); setErr('') }
  }

  async function handleValidate() {
    if (!file) return
    setValidating(true); setErr(''); setImportResult(null)
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await api.kb.bulkValidate(fd)
      setValidateResult(res)
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : 'Validation failed') }
    finally { setValidating(false) }
  }

  async function handleImport() {
    if (!file) return
    if (!confirm(`Import ${file.name}? This will add entries to the knowledge base.`)) return
    setImporting(true); setErr('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await api.kb.bulkImport(fd)
      setImportResult(res)
      setValidateResult(null)
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : 'Import failed') }
    finally { setImporting(false) }
  }

  function handleDownloadTemplate() {
    window.open('/api/v1/admin/kb/templates/csv', '_blank')
  }

  return (
    <div className="space-y-4 max-w-2xl">
      {/* Download template */}
      <div className="glass-panel p-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-700">CSV Import Template</p>
          <p className="text-xs text-slate-400 mt-0.5">Download the template to see required columns and format.</p>
        </div>
        <button onClick={handleDownloadTemplate}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-ub-blue text-white rounded-lg hover:bg-ub-blue-dark transition-colors font-medium">
          <Download size={14} />Download Template
        </button>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`glass-panel p-10 border-2 border-dashed rounded-2xl flex flex-col items-center gap-3 cursor-pointer transition-colors ${dragging ? 'border-ub-blue bg-ub-blue-light/40' : 'border-slate-200 hover:border-slate-300'}`}
        onClick={() => fileRef.current?.click()}
      >
        <Upload size={28} className={dragging ? 'text-ub-blue' : 'text-slate-300'} />
        {file ? (
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-700">{file.name}</p>
            <p className="text-xs text-slate-400 mt-0.5">{(file.size / 1024).toFixed(1)} KB · click to change</p>
          </div>
        ) : (
          <div className="text-center">
            <p className="text-sm font-medium text-slate-500">Drop a CSV or JSON file here</p>
            <p className="text-xs text-slate-400 mt-1">or click to browse</p>
          </div>
        )}
        <input ref={fileRef} type="file" accept=".csv,.json" className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) { setFile(f); setValidateResult(null); setImportResult(null); setErr('') } }} />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button onClick={handleValidate} disabled={!file || validating}
          className="flex items-center gap-2 px-4 py-2 text-sm border border-slate-200 bg-white rounded-lg hover:bg-slate-50 transition-colors font-medium disabled:opacity-40">
          {validating ? <RefreshCw size={14} className="animate-spin" /> : <CheckCircle2 size={14} className="text-emerald-500" />}
          Validate File
        </button>
        <button onClick={handleImport} disabled={!file || importing || (!!validateResult && validateResult.errors > 0)}
          className="flex items-center gap-2 px-5 py-2 text-sm bg-ub-blue text-white rounded-lg hover:bg-ub-blue-dark transition-colors font-medium disabled:opacity-40">
          {importing ? <RefreshCw size={14} className="animate-spin" /> : <Upload size={14} />}
          Import to KB
        </button>
      </div>

      {err && <div className="text-xs text-red-500 bg-red-50 rounded-lg px-4 py-2">{err}</div>}

      {/* Import result */}
      {importResult && (
        <div className="glass-panel p-4 border border-emerald-200 bg-emerald-50/40">
          <div className="flex items-center gap-2 mb-2"><CheckCircle2 size={16} className="text-emerald-500" /><p className="text-sm font-semibold text-emerald-700">Import Complete</p></div>
          <p className="text-xs text-slate-600">{importResult.successful ?? '?'} entries imported · {importResult.failed ?? 0} errors</p>
        </div>
      )}

      {/* Validate result */}
      {validateResult && (
        <div className="glass-panel p-4 space-y-3">
          <div className="flex items-center gap-4">
            <p className="text-sm font-semibold text-slate-700">Validation Results</p>
            <span className="text-xs text-emerald-600 font-medium">{validateResult.valid} valid</span>
            {validateResult.errors > 0 && <span className="text-xs text-red-500 font-medium">{validateResult.errors} errors</span>}
          </div>
          <div className="overflow-x-auto max-h-64 overflow-y-auto border border-slate-100 rounded-xl">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 border-b border-slate-100">
                <tr>
                  <th className="px-3 py-2 text-left text-slate-400 font-medium">Row</th>
                  <th className="px-3 py-2 text-left text-slate-400 font-medium">Status</th>
                  <th className="px-3 py-2 text-left text-slate-400 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {validateResult.rows.map((r: Record<string, unknown>, i) => (
                  <tr key={i} className="border-b border-slate-50">
                    <td className="px-3 py-1.5 text-slate-500">{i + 1}</td>
                    <td className="px-3 py-1.5">
                      {r.valid || !r.error
                        ? <span className="text-emerald-600 font-medium">✓ Valid</span>
                        : <span className="text-red-500 font-medium">✗ Error</span>}
                    </td>
                    <td className="px-3 py-1.5 text-slate-500">{String(r.error ?? r.message ?? r.category ?? '—')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Jobs Sub-tab ───────────────────────────────────────────────────────────────

interface JobCardProps {
  icon: React.ReactNode
  title: string
  description: string
  onRun: () => Promise<unknown>
}

function JobCard({ icon, title, description, onRun }: JobCardProps) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null)

  async function run() {
    setLoading(true); setResult(null)
    try {
      await onRun()
      setResult({ ok: true, msg: 'Job triggered successfully.' })
    } catch (e: unknown) {
      setResult({ ok: false, msg: e instanceof Error ? e.message : 'Job failed' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="glass-panel p-5 flex items-start gap-4">
      <div className="w-10 h-10 bg-ub-blue-light rounded-xl flex items-center justify-center flex-shrink-0 text-ub-blue">{icon}</div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-700 mb-1">{title}</p>
        <p className="text-xs text-slate-400 leading-relaxed">{description}</p>
        {result && (
          <p className={`text-xs mt-2 font-medium ${result.ok ? 'text-emerald-600' : 'text-red-500'}`}>
            {result.ok ? '✓' : '✗'} {result.msg}
          </p>
        )}
      </div>
      <button onClick={run} disabled={loading}
        className="flex items-center gap-2 px-4 py-2 text-sm bg-ub-blue text-white rounded-lg hover:bg-ub-blue-dark transition-colors font-medium disabled:opacity-50 flex-shrink-0">
        {loading ? <RefreshCw size={14} className="animate-spin" /> : <Zap size={14} />}
        {loading ? 'Running…' : 'Run'}
      </button>
    </div>
  )
}

function JobsSection() {
  return (
    <div className="space-y-3 max-w-2xl">
      <div className="glass-panel p-4 border border-amber-200 bg-amber-50/40 text-xs text-amber-700 flex items-center gap-2">
        <AlertTriangle size={14} />
        These jobs run immediately. Use with caution — they may modify knowledge base data.
      </div>
      <JobCard
        icon={<Settings2 size={18} />}
        title="Process Queue"
        description="Manually trigger queue processing — auto-approves high-quality entries (≥ 0.95 quality score) and logs results."
        onRun={() => api.kb.processQueue()}
      />
      <JobCard
        icon={<Shield size={18} />}
        title="Weekly Review Digest"
        description="Trigger the weekly unverified-entry digest, which emails a summary of entries awaiting verification to admins."
        onRun={() => api.kb.weeklyReview()}
      />
      <JobCard
        icon={<Trash2 size={18} />}
        title="Cleanup Old Entries"
        description="Remove stale processed queue entries that are older than the retention window (default: 30 days)."
        onRun={() => api.kb.cleanup()}
      />
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────────

const SUB_TABS: { id: SubTab; label: string; icon: React.ReactNode }[] = [
  { id: 'overview',  label: 'Overview',  icon: <LayoutDashboard size={14} /> },
  { id: 'entries',   label: 'Entries',   icon: <List size={14} /> },
  { id: 'queue',     label: 'Queue',     icon: <Clock4 size={14} /> },
  { id: 'analytics', label: 'Analytics', icon: <BarChart2 size={14} /> },
  { id: 'import',    label: 'Import',    icon: <Upload size={14} /> },
  { id: 'jobs',      label: 'Jobs',      icon: <Settings2 size={14} /> },
]

export function KBAdminTab() {
  const [subTab, setSubTab] = useState<SubTab>('overview')
  const [metricsTick, setMetricsTick] = useState(0)

  const { data: refData } = useApiData<KBReference>(() => api.kb.reference(), [])
  const { data: metrics, loading: metricsLoading } = useApiData<KBMetrics>(() => api.kb.metrics(), [metricsTick])

  const refresh = useCallback(() => setMetricsTick(t => t + 1), [])

  const queueCount = metrics?.pending ?? 0

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="glass-panel p-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-ub-blue rounded-xl flex items-center justify-center">
            <BookOpen size={16} className="text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-800">Knowledge Base Admin</h1>
            <p className="text-xs text-slate-400">Manage resolution entries · review AI-generated content · import data</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {metrics && (
            <div className="flex items-center gap-3 text-xs">
              <span className="px-2.5 py-1 bg-ub-blue-light text-ub-blue rounded-full font-semibold border border-ub-blue/20">
                {metrics.total} total
              </span>
              <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-full font-semibold border border-emerald-200">
                {metrics.verified} verified
              </span>
              {metrics.pending > 0 && (
                <span className="px-2.5 py-1 bg-amber-50 text-amber-700 rounded-full font-semibold border border-amber-200 animate-pulse">
                  {metrics.pending} pending
                </span>
              )}
            </div>
          )}
          <button onClick={refresh} disabled={metricsLoading}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-400 transition-colors disabled:opacity-40">
            <RefreshCw size={14} className={metricsLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Sub-tab nav */}
      <div className="flex items-center gap-1 bg-white/60 backdrop-blur-sm rounded-xl border border-slate-200/80 p-1 w-fit">
        {SUB_TABS.map(t => {
          const isActive = subTab === t.id
          const hasBadge = t.id === 'queue' && queueCount > 0
          return (
            <button
              key={t.id}
              onClick={() => setSubTab(t.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                isActive ? 'bg-ub-blue text-white shadow-sm' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100/80'
              }`}
            >
              {t.icon}
              {t.label}
              {hasBadge && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${isActive ? 'bg-white/20 text-white' : 'bg-amber-100 text-amber-700'}`}>
                  {queueCount}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Content */}
      {subTab === 'overview'  && <OverviewSection metrics={metrics} refData={refData} />}
      {subTab === 'entries'   && <EntriesSection refData={refData} />}
      {subTab === 'queue'     && <QueueSection refData={refData} />}
      {subTab === 'analytics' && <AnalyticsSection />}
      {subTab === 'import'    && <ImportSection />}
      {subTab === 'jobs'      && <JobsSection />}
    </div>
  )
}

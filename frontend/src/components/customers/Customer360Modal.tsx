import { useState, useEffect } from "react";
import { X, User, FileText, Clock, MessageSquare, Reply, AlertCircle, StickyNote, BarChart2, ChevronRight } from "lucide-react";
import { api } from "../../lib/api";
import type { CustomerDetail, Channel, Status } from "../../types";
import { getInitials } from "../../utils/styles";
import { StatusBadge } from "../ui/StatusBadge";
import { ChannelBadge } from "../ui/ChannelBadge";
import { CustomerSummaryCard } from "./CustomerSummaryCard";

type Tab = "overview" | "complaints" | "timeline" | "communication" | "replies" | "followups" | "notes" | "analytics";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <User size={13} /> },
  { id: "complaints", label: "Complaints", icon: <FileText size={13} /> },
  { id: "timeline", label: "Timeline", icon: <Clock size={13} /> },
  { id: "communication", label: "Communication", icon: <MessageSquare size={13} /> },
  { id: "replies", label: "Replies", icon: <Reply size={13} /> },
  { id: "followups", label: "Follow-ups", icon: <AlertCircle size={13} /> },
  { id: "notes", label: "Notes", icon: <StickyNote size={13} /> },
  { id: "analytics", label: "Analytics", icon: <BarChart2 size={13} /> },
];

interface Props {
  cifId: string;
  onClose: () => void;
}

function DonutChart({ data }: { data: { category: string; count: number }[] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  if (!total) return <p className="text-xs text-slate-400">No complaint data</p>;
  const colors = ["#003087", "#244f9e", "#456fad", "#6b8fbf", "#94adc9", "#bcccdc"];
  return (
    <div className="space-y-1.5">
      {data.slice(0, 6).map((d, i) => (
        <div key={d.category} className="flex items-center gap-2 text-xs">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: colors[i % colors.length] }} />
          <span className="flex-1 truncate text-slate-600">{d.category}</span>
          <span className="font-semibold text-slate-700">{d.count}</span>
          <span className="text-slate-400">({Math.round((d.count / total) * 100)}%)</span>
        </div>
      ))}
    </div>
  );
}

export function Customer360Modal({ cifId, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [data, setData] = useState<CustomerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api.customers.get(cifId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [cifId]);

  const initials = data ? getInitials(data.profile.name) : "?";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-4 px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-ub-blue/5 to-white flex-shrink-0">
          {data && (
            <>
              <div className="w-12 h-12 rounded-full bg-ub-blue text-white flex items-center justify-center text-base font-bold flex-shrink-0">
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-base font-semibold text-slate-800">{data.profile.name}</h2>
                <p className="text-xs text-slate-400 font-mono">{data.profile.cif_id}</p>
              </div>
              <div className="flex gap-3 text-center flex-shrink-0">
                {[
                  { label: "Total", value: data.stats.total_complaints, color: "text-slate-700" },
                  { label: "Active", value: data.stats.active_complaints, color: "text-amber-600" },
                  { label: "Resolved", value: data.stats.resolved_complaints, color: "text-emerald-600" },
                ].map((s) => (
                  <div key={s.label} className="px-3 py-1 bg-white border border-slate-200 rounded-lg">
                    <p className={`text-base font-bold ${s.color}`}>{s.value}</p>
                    <p className="text-[10px] text-slate-400">{s.label}</p>
                  </div>
                ))}
              </div>
            </>
          )}
          {loading && <p className="text-sm text-slate-400">Loading customer data…</p>}
          <button onClick={onClose} className="ml-2 p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 flex-shrink-0">
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 border-b border-slate-200 px-4 flex-shrink-0 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === t.id
                  ? "border-ub-blue text-ub-blue"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading && (
            <div className="flex items-center justify-center h-32">
              <p className="text-sm text-slate-400">Loading…</p>
            </div>
          )}
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
          )}
          {!loading && !error && data && (
            <>
              {activeTab === "overview" && <OverviewTab data={data} />}
              {activeTab === "complaints" && <ComplaintsTab data={data} />}
              {activeTab === "timeline" && <TimelineTab data={data} />}
              {activeTab === "communication" && <CommunicationTab data={data} />}
              {activeTab === "replies" && <RepliesTab data={data} />}
              {activeTab === "followups" && <FollowupsTab data={data} />}
              {activeTab === "notes" && <NotesTab data={data} />}
              {activeTab === "analytics" && <AnalyticsTab data={data} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Tab panels ────────────────────────────────────────────────────────────────

function OverviewTab({ data }: { data: CustomerDetail }) {
  const { profile, stats, insights, timeline_events, category_breakdown } = data;
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Customer narrative summary */}
      <div className="md:col-span-3">
        <CustomerSummaryCard cifId={profile.cif_id} />
      </div>

      {/* Customer profile */}
      <div className="bg-slate-50 rounded-xl p-4 space-y-2">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Customer Profile</h3>
        {[
          { label: "CIF ID", value: profile.cif_id },
          { label: "Email", value: profile.email },
          { label: "Phone", value: profile.phone },
          { label: "Account", value: profile.account_number },
          { label: "Customer since", value: profile.customer_since },
          { label: "KYC Verified", value: profile.verified ? "Yes" : "No" },
        ].map((r) => r.value && (
          <div key={r.label} className="flex justify-between text-xs">
            <span className="text-slate-400">{r.label}</span>
            <span className="font-medium text-slate-700 text-right max-w-[160px] truncate">{String(r.value)}</span>
          </div>
        ))}
        <div className="pt-2 border-t border-slate-200">
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Avg resolution</span>
            <span className="font-medium text-slate-700">{stats.avg_resolution_days != null ? `${stats.avg_resolution_days}d` : "—"}</span>
          </div>
        </div>
      </div>

      {/* Complaint breakdown */}
      <div className="bg-slate-50 rounded-xl p-4 space-y-3">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Complaint Categories</h3>
        <DonutChart data={category_breakdown} />
        <div className="pt-2 border-t border-slate-200 space-y-1">
          {[
            { label: "Total", value: stats.total_complaints },
            { label: "Merged duplicates", value: stats.merged_complaints },
          ].map((r) => (
            <div key={r.label} className="flex justify-between text-xs">
              <span className="text-slate-400">{r.label}</span>
              <span className="font-semibold text-slate-700">{r.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Insights + timeline strip */}
      <div className="space-y-4">
        <div className="bg-amber-50 border border-amber-100 rounded-xl p-4 space-y-2">
          <h3 className="text-xs font-semibold text-amber-700 uppercase tracking-wide">Key Insights</h3>
          {insights.length === 0
            ? <p className="text-xs text-slate-400">No insights available</p>
            : insights.map((ins, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-amber-800">
                <ChevronRight size={11} className="mt-0.5 flex-shrink-0" />
                <span>{ins}</span>
              </div>
            ))}
        </div>
        <div className="bg-slate-50 rounded-xl p-4">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Recent Events</h3>
          <div className="space-y-1.5">
            {timeline_events.slice(-5).reverse().map((e, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-ub-blue flex-shrink-0" />
                <span className="flex-1 text-slate-600">{e.event}</span>
                <span className="text-slate-400 text-[10px] flex-shrink-0">{(e.timestamp || "").slice(0, 10)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ComplaintsTab({ data }: { data: CustomerDetail }) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-400">{data.complaints.length} complaint{data.complaints.length !== 1 ? "s" : ""}</p>
      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              {["ID", "Channel", "Category", "Status", "Severity", "Sentiment", "Date"].map((h) => (
                <th key={h} className="px-3 py-2 text-left font-semibold text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.complaints.map((c: Record<string, unknown>) => (
              <tr key={String(c.complaint_id)} className="hover:bg-slate-50 transition-colors">
                <td className="px-3 py-2 font-mono text-slate-500 max-w-[100px] truncate">{String(c.complaint_id ?? "").slice(0, 8)}…</td>
                <td className="px-3 py-2"><ChannelBadge channel={String(c.channel ?? "") as Channel} /></td>
                <td className="px-3 py-2 text-slate-600">{String(c.category ?? "—")}</td>
                <td className="px-3 py-2"><StatusBadge status={String(c.status ?? "") as Status} /></td>
                <td className="px-3 py-2 text-slate-500">{c.severity != null ? String(c.severity) : "—"}</td>
                <td className="px-3 py-2 text-slate-500">{String(c.sentiment ?? "—")}</td>
                <td className="px-3 py-2 text-slate-400">{String(c.created_at ?? "").slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.complaints.length === 0 && (
          <p className="text-center py-8 text-sm text-slate-400">No complaints found</p>
        )}
      </div>
    </div>
  );
}

function TimelineTab({ data }: { data: CustomerDetail }) {
  const events = [...data.timeline_events].sort((a, b) => (a.timestamp ?? "").localeCompare(b.timestamp ?? ""));
  const eventColors: Record<string, string> = {
    "Complaint Received": "bg-ub-blue",
    "Auto Acknowledgement": "bg-emerald-500",
    "Agent Reply": "bg-amber-500",
    "Escalated": "bg-red-500",
    "Resolved": "bg-emerald-600",
  };
  return (
    <div className="space-y-0">
      {events.length === 0 && <p className="text-sm text-slate-400">No timeline events</p>}
      {events.map((e, i) => (
        <div key={i} className="flex gap-3 pb-4">
          <div className="flex flex-col items-center">
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 mt-0.5 ${eventColors[e.event] ?? "bg-slate-300"}`} />
            {i < events.length - 1 && <span className="w-px flex-1 bg-slate-200 mt-1" />}
          </div>
          <div className="flex-1 min-w-0 pb-1">
            <div className="flex items-baseline gap-2">
              <span className="text-xs font-medium text-slate-700">{e.event}</span>
              <span className="text-[10px] text-slate-400">{(e.timestamp ?? "").slice(0, 16).replace("T", " ")}</span>
            </div>
            <div className="flex gap-2 mt-0.5">
              {e.channel && <span className="text-[10px] text-slate-400">{e.channel}</span>}
              {e.complaint_id && <span className="text-[10px] font-mono text-slate-400">{String(e.complaint_id).slice(0, 8)}…</span>}
              {e.tier != null && <span className="text-[10px] text-slate-400">Tier {e.tier}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function CommunicationTab({ data }: { data: CustomerDetail }) {
  const events = [...data.timeline_events].sort((a, b) => (a.timestamp ?? "").localeCompare(b.timestamp ?? ""));
  return (
    <div className="space-y-3">
      {events.length === 0 && <p className="text-sm text-slate-400">No communication history</p>}
      {events.map((e, i) => (
        <div key={i} className="flex gap-3 p-3 bg-slate-50 rounded-lg">
          <div className="flex flex-col items-center gap-1">
            <span className="text-[10px] text-slate-400 whitespace-nowrap">{(e.timestamp ?? "").slice(0, 10)}</span>
          </div>
          <div className="flex-1">
            <p className="text-xs font-medium text-slate-700">{e.event}</p>
            {e.channel && <p className="text-[11px] text-slate-400 mt-0.5">{e.channel}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

function RepliesTab({ data }: { data: CustomerDetail }) {
  return (
    <div className="space-y-3">
      {data.replies.length === 0 && <p className="text-sm text-slate-400">No replies found</p>}
      {data.replies.map((r, i) => (
        <div key={i} className="border border-slate-200 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <ChannelBadge channel={(r.channel ?? "") as Channel} />
            <span className="text-[10px] font-mono text-slate-400">{String(r.complaint_id).slice(0, 8)}…</span>
            <span className="ml-auto text-[10px] text-slate-400">{(r.timestamp ?? "").slice(0, 10)}</span>
          </div>
          <p className="text-xs text-slate-700 whitespace-pre-wrap line-clamp-6">{r.reply}</p>
          {r.route && (
            <span className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-ub-blue/10 text-ub-blue font-medium">
              {r.route}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function FollowupsTab({ data }: { data: CustomerDetail }) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-400">{data.followups.length} follow-up complaint{data.followups.length !== 1 ? "s" : ""} detected</p>
      {data.followups.length === 0 && <p className="text-sm text-slate-400">No follow-up complaints detected</p>}
      {data.followups.map((f, i) => (
        <div key={i} className="border border-amber-200 bg-amber-50 rounded-xl p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-slate-600">{String(f.complaint_id).slice(0, 8)}…</span>
            {f.channel && <ChannelBadge channel={f.channel as Channel} />}
            <span className="ml-auto text-[10px] text-slate-400">{(f.timestamp ?? "").slice(0, 10)}</span>
          </div>
          {f.duplicate_of && (
            <p className="text-xs text-amber-700">
              Duplicate of: <span className="font-mono">{String(f.duplicate_of).slice(0, 8)}…</span>
            </p>
          )}
          {f.category && <p className="text-xs text-slate-600">{f.category}</p>}
          {f.status && <StatusBadge status={f.status as Status} />}
        </div>
      ))}
    </div>
  );
}

function NotesTab({ data }: { data: CustomerDetail }) {
  return (
    <div className="space-y-3">
      {data.notes.length === 0 && <p className="text-sm text-slate-400">No internal notes</p>}
      {data.notes.map((n, i) => (
        <div key={i} className="border border-slate-200 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
              n.type === "escalation" ? "bg-red-50 text-red-600 border border-red-200" : "bg-slate-100 text-slate-600"
            }`}>{n.type}</span>
            <span className="ml-auto text-[10px] text-slate-400">{String(n.complaint_id).slice(0, 8)}…</span>
            <span className="text-[10px] text-slate-400">{(n.timestamp ?? "").slice(0, 10)}</span>
          </div>
          <p className="text-xs text-slate-700 whitespace-pre-wrap line-clamp-6">
            {Array.isArray(n.content) ? n.content.join(" → ") : String(n.content)}
          </p>
        </div>
      ))}
    </div>
  );
}

function AnalyticsTab({ data }: { data: CustomerDetail }) {
  const { stats, sentiment_trend, category_breakdown } = data;
  const sentimentCounts = sentiment_trend.reduce<Record<string, number>>((acc, s) => {
    acc[s.sentiment] = (acc[s.sentiment] ?? 0) + 1;
    return acc;
  }, {});
  const negativeEmotions = ["angry", "furious", "frustrated", "upset", "stressed"];
  const negCount = Object.entries(sentimentCounts)
    .filter(([k]) => negativeEmotions.includes(k.toLowerCase()))
    .reduce((s, [, v]) => s + v, 0);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="bg-slate-50 rounded-xl p-4 space-y-3">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Key Metrics</h3>
        {[
          { label: "Total Complaints", value: String(stats.total_complaints) },
          { label: "Active", value: String(stats.active_complaints) },
          { label: "Resolved", value: String(stats.resolved_complaints) },
          { label: "Merged/Duplicates", value: String(stats.merged_complaints) },
          { label: "Avg Resolution", value: stats.avg_resolution_days != null ? `${stats.avg_resolution_days}d` : "—" },
          { label: "Negative Sentiment", value: String(negCount) },
        ].map((r) => (
          <div key={r.label} className="flex justify-between text-xs">
            <span className="text-slate-400">{r.label}</span>
            <span className="font-semibold text-slate-700">{r.value}</span>
          </div>
        ))}
      </div>
      <div className="bg-slate-50 rounded-xl p-4 space-y-3">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Category Breakdown</h3>
        <DonutChart data={category_breakdown} />
      </div>
      <div className="bg-slate-50 rounded-xl p-4 col-span-full space-y-3">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Sentiment Distribution</h3>
        <div className="flex flex-wrap gap-2">
          {Object.entries(sentimentCounts).map(([sentiment, count]) => (
            <div key={sentiment} className="flex items-center gap-1.5 px-2.5 py-1 bg-white border border-slate-200 rounded-full text-xs">
              <span className="text-slate-600">{sentiment}</span>
              <span className="font-semibold text-slate-800">{count}</span>
            </div>
          ))}
          {Object.keys(sentimentCounts).length === 0 && (
            <p className="text-xs text-slate-400">No sentiment data available</p>
          )}
        </div>
      </div>
    </div>
  );
}

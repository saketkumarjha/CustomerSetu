import {
  Inbox,
  AlertCircle,
  CheckCircle2,
  TrendingUp,
  RefreshCw,
  Shield,
  Copy,
  Zap,
  Layers,
} from "lucide-react";
import type { TabId } from "../../types";
import { KpiCard } from "./KpiCard";
import { RecentComplaintsFeed } from "./RecentComplaintsFeed";
import { ChannelBar } from "./ChannelBar";
import { AiMetrics } from "./AiMetrics";
import { api } from "../../lib/api";
import { useApiData } from "../../hooks/useApiData";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from "recharts";

interface Props {
  setActive: (id: TabId) => void;
}

// ── Tier config ───────────────────────────────────────────────────────────────
const TIER_LABELS: Record<number, string> = {
  0: "Auto",
  1: "Branch",
  2: "Zonal",
  3: "Regional",
  4: "Head Office",
  5: "RBI",
};
const TIER_COLORS: Record<number, string> = {
  0: "#10b981",
  1: "#003087",
  2: "#6366f1",
  3: "#f59e0b",
  4: "#ef4444",
  5: "#7c3aed",
};

// ── Mock channel fallback ─────────────────────────────────────────────────────
const FALLBACK_CHANNEL_STATS = [
  { channel: "Email", count: 0, color: "#003087", total: 1 },
  { channel: "Phone", count: 0, color: "#003087", total: 1 },
  { channel: "Web Form", count: 0, color: "#003087", total: 1 },
  { channel: "Mobile App", count: 0, color: "#003087", total: 1 },
  { channel: "Social Media", count: 0, color: "#003087", total: 1 },
];

// ── Stat pill ─────────────────────────────────────────────────────────────────
function StatPill({
  icon,
  label,
  value,
  color = "slate",
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  color?: "slate" | "red" | "amber" | "emerald" | "violet" | "blue";
}) {
  const styles = {
    slate: "bg-slate-50 border-slate-200 text-slate-700",
    red: "bg-red-50 border-red-200 text-red-700",
    amber: "bg-amber-50 border-amber-200 text-amber-700",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-700",
    violet: "bg-violet-50 border-violet-200 text-violet-700",
    blue: "bg-blue-50 border-blue-200 text-blue-700",
  };
  return (
    <div
      className={`flex items-center gap-2.5 rounded-xl border px-3 py-2.5 ${styles[color]}`}
    >
      <div className="flex-shrink-0 opacity-70">{icon}</div>
      <div>
        <div className="text-lg font-bold tabular-nums leading-none">
          {value}
        </div>
        <div className="text-[11px] font-medium mt-0.5 opacity-80">{label}</div>
      </div>
    </div>
  );
}

export function OverviewTab({ setActive }: Props) {
  const {
    data: stats,
    loading,
    error,
    refetch,
  } = useApiData(() => api.dashboard.stats(30), []);

  // Fetch the 8 most recent complaints for the feed
  const { data: recentData, loading: recentLoading } = useApiData(
    () => api.complaints.list({ limit: 8 }),
    [],
  );

  const recentComplaints = recentData?.complaints ?? [];

  const totalComplaints = stats?.overview?.total_complaints ?? 0;
  const openCount = stats?.overview?.open ?? 0;
  const resolvedCount = stats?.overview?.closed ?? 0;
  const autoRate = stats?.overview?.auto_respond_rate_percent ?? 0;
  const rbiCount = stats?.overview?.rbi_reportable ?? 0;
  const duplicateCount = stats?.overview?.duplicate_count ?? 0;
  const autoSentCount =
    stats?.overview?.auto_sent_count ?? stats?.overview?.auto_responded ?? 0;
  const humanReview = stats?.overview?.human_review ?? 0;

  const channelStats =
    stats?.distributions?.by_channel?.map((c) => ({
      channel: c.channel,
      count: c.count,
      color: "#003087",
      total: totalComplaints,
    })) ?? FALLBACK_CHANNEL_STATS;

  const tierData = stats?.distributions?.by_tier ?? [];
  const dailyVolume = stats?.daily_volume ?? [];

  return (
    <div className="space-y-4 md:space-y-5">
      {/* Offline banner */}
      {error && (
        <div className="glass-panel border-amber-200/80 px-4 py-2.5 flex items-center justify-between text-xs text-amber-900">
          <span>Showing demo data — could not connect to backend</span>
          <button
            onClick={refetch}
            className="flex items-center gap-1 font-medium hover:underline"
          >
            <RefreshCw size={11} /> Retry
          </button>
        </div>
      )}

      {/* ── KPI row ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <KpiCard
          icon={<Inbox size={17} />}
          label="Total Complaints"
          value={loading ? "…" : totalComplaints}
          sub="Last 30 days"
          trend={stats ? `${autoRate}% auto-resolved` : undefined}
        />
        <KpiCard
          icon={<AlertCircle size={17} />}
          label="Open / Active"
          value={loading ? "…" : openCount}
          sub="Needs attention"
          trend={stats ? `${humanReview} in review` : undefined}
        />
        <KpiCard
          icon={<Zap size={17} />}
          label="Auto-Sent"
          value={loading ? "…" : autoSentCount}
          sub="Sent without human review"
          trend={stats ? `${autoRate}% rate` : undefined}
          trendUp={autoRate > 50}
        />
        <KpiCard
          icon={<CheckCircle2 size={17} />}
          label="Resolved"
          value={loading ? "…" : resolvedCount}
          sub="Closed & resolved"
          trend={
            stats
              ? `${stats.overview?.rbi_reportable_rate_percent ?? 0}% RBI rate`
              : undefined
          }
        />
      </div>

      {/* ── Secondary stat pills ── */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatPill
            icon={<Shield size={14} />}
            label="RBI Reportable"
            value={rbiCount}
            color="red"
          />
          <StatPill
            icon={<Copy size={14} />}
            label="Duplicates Detected"
            value={duplicateCount}
            color="amber"
          />
          <StatPill
            icon={<Zap size={14} />}
            label="Auto-Sent to Customer"
            value={autoSentCount}
            color="emerald"
          />
          <StatPill
            icon={<AlertCircle size={14} />}
            label="Pending Human Review"
            value={humanReview}
            color="blue"
          />
        </div>
      )}

      {/* ── Daily volume chart ── */}
      {dailyVolume.length > 0 && (
        <div className="glass-panel p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs font-semibold text-slate-800 flex items-center gap-2">
              <TrendingUp size={13} className="text-ub-blue" />
              Complaint Volume — Last 7 Days
            </div>
            <div className="text-[10px] text-slate-400">Live database</div>
          </div>
          <ResponsiveContainer width="100%" height={130}>
            <AreaChart
              data={dailyVolume}
              margin={{ top: 4, right: 4, left: -24, bottom: 0 }}
            >
              <defs>
                <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#003087" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#003087" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10 }}
                tickLine={false}
                tickFormatter={(d) => d.slice(5)}
              />
              <YAxis
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  fontSize: 11,
                  borderRadius: 8,
                  border: "1px solid #e2e8f0",
                }}
                labelFormatter={(l) => `Date: ${l}`}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#003087"
                fill="url(#blueGrad)"
                strokeWidth={2}
                name="Complaints"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Tier distribution + Category distribution ── */}
      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Tier distribution */}
          {tierData.length > 0 && (
            <div className="glass-panel p-4">
              <div className="flex items-center gap-2 mb-4">
                <Layers size={13} className="text-ub-blue" />
                <div className="text-xs font-semibold text-slate-800">
                  Complaints by Tier
                </div>
              </div>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart
                  data={tierData}
                  margin={{ top: 4, right: 4, left: -24, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#F1F5F9"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="tier"
                    tick={{ fontSize: 10 }}
                    tickLine={false}
                    tickFormatter={(t) => TIER_LABELS[t] ?? `T${t}`}
                  />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      fontSize: 11,
                      borderRadius: 8,
                      border: "1px solid #e2e8f0",
                    }}
                    formatter={(v, _n, p) => [
                      v,
                      TIER_LABELS[p.payload.tier] ?? `Tier ${p.payload.tier}`,
                    ]}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {tierData.map((entry) => (
                      <Cell
                        key={entry.tier}
                        fill={TIER_COLORS[entry.tier] ?? "#6B7280"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {/* Legend */}
              <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
                {tierData.map((t) => (
                  <div
                    key={t.tier}
                    className="flex items-center gap-1 text-[10px] text-slate-500"
                  >
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: TIER_COLORS[t.tier] ?? "#6B7280" }}
                    />
                    {TIER_LABELS[t.tier] ?? `Tier ${t.tier}`}
                    <span className="font-semibold text-slate-700">
                      {t.count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Category distribution */}
          <div className="glass-panel p-4">
            <div className="text-xs font-semibold text-slate-800 mb-4">
              Top Categories
            </div>
            <div className="space-y-2">
              {(stats.distributions?.by_category ?? [])
                .slice(0, 6)
                .map((cat) => (
                  <div key={cat.category}>
                    <div className="flex justify-between text-xs mb-0.5">
                      <span className="text-slate-600 truncate pr-2">
                        {cat.category}
                      </span>
                      <span className="font-semibold text-slate-800 tabular-nums flex-shrink-0">
                        {cat.count}{" "}
                        <span className="text-slate-400 font-normal">
                          ({cat.percent}%)
                        </span>
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-ub-blue/75 transition-all duration-700"
                        style={{ width: `${cat.percent}%` }}
                      />
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Main content: recent feed + sidebar ── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 md:gap-5">
        <div className="xl:col-span-2">
          <RecentComplaintsFeed
            complaints={recentComplaints}
            loading={recentLoading}
            setActive={setActive}
          />
        </div>
        <div className="flex flex-col gap-4">
          <ChannelBar stats={channelStats} />
          <AiMetrics
            autoRate={autoRate}
            rbiCount={rbiCount}
            confidence={stats?.averages?.avg_confidence_score}
            duplicateCount={duplicateCount}
            autoSentCount={autoSentCount}
            totalComplaints={totalComplaints}
          />
        </div>
      </div>
    </div>
  );
}

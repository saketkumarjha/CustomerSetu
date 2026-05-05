import { Inbox, AlertCircle, AlertTriangle, CheckCircle2, TrendingUp, RefreshCw } from 'lucide-react'
import type { TabId } from '../../types'
import { COMPLAINTS } from '../../data/complaints'
import { KpiCard } from './KpiCard'
import { RecentComplaintsFeed } from './RecentComplaintsFeed'
import { ChannelBar } from './ChannelBar'
import { AiMetrics } from './AiMetrics'
import { api } from '../../lib/api'
import { useApiData } from '../../hooks/useApiData'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts'

interface Props {
  setActive: (id: TabId) => void
}

const CHANNEL_COLORS: Record<string, string> = {
  Email: '#003087',
  Phone: '#C8102E',
  'Web Form': '#0052CC',
  'Mobile App': '#7C3AED',
  'Social Media': '#EA580C',
}

// Mock channel data from static COMPLAINTS as fallback
const MOCK_CHANNEL_STATS = (() => {
  const counts = COMPLAINTS.reduce<Record<string, number>>((acc, c) => {
    acc[c.channel] = (acc[c.channel] ?? 0) + 1
    return acc
  }, {})
  return Object.entries(counts).map(([channel, count]) => ({
    channel: channel as import('../../types').Channel,
    count,
    color: CHANNEL_COLORS[channel] ?? '#6B7280',
    total: COMPLAINTS.length,
  }))
})()

export function OverviewTab({ setActive }: Props) {
  const { data: stats, loading, error, refetch } = useApiData(
    () => api.dashboard.stats(30),
    [],
  )

  // Use API data if available, fall back to mock counts
  const totalComplaints = stats?.overview.total_complaints ?? COMPLAINTS.length
  const openCount = stats?.overview.open ?? COMPLAINTS.filter((c) => c.status === 'Open' || c.status === 'In Progress').length
  const breachedCount = stats
    ? stats.overview.human_review  // as proxy when using API
    : COMPLAINTS.filter((c) => c.slaBreached).length
  const resolvedCount = stats?.overview.closed ?? COMPLAINTS.filter((c) => c.status === 'Resolved').length
  const autoRate = stats?.overview.auto_respond_rate_percent ?? 38

  const channelStats = stats?.distributions.by_channel.map((c) => ({
    channel: c.channel as import('../../types').Channel,
    count: c.count,
    color: CHANNEL_COLORS[c.channel] ?? '#6B7280',
    total: totalComplaints,
  })) ?? MOCK_CHANNEL_STATS

  const dailyVolume = stats?.daily_volume ?? []

  return (
    <div className="space-y-4 md:space-y-5">
      {/* API status banner */}
      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-2.5 flex items-center justify-between text-xs text-amber-700">
          <span>Showing demo data — could not connect to backend</span>
          <button onClick={refetch} className="flex items-center gap-1 font-medium hover:underline">
            <RefreshCw size={11} /> Retry
          </button>
        </div>
      )}

      {/* KPI row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <KpiCard
          icon={<Inbox size={18} />}
          label="Total Complaints"
          value={loading ? '…' : totalComplaints}
          sub="Last 30 days"
          valueColor="#003087"
          trend={stats ? `${stats.overview.auto_respond_rate_percent}% auto-resolved` : '-8%'}
          trendUp={false}
        />
        <KpiCard
          icon={<AlertCircle size={18} />}
          label="Open / Active"
          value={loading ? '…' : openCount}
          sub="Needs attention"
          valueColor="#C8102E"
          trend={stats ? `${stats.overview.human_review} pending review` : '+12%'}
          trendUp={true}
        />
        <KpiCard
          icon={<AlertTriangle size={18} />}
          label={stats ? 'Awaiting Review' : 'SLA Breached'}
          value={loading ? '…' : breachedCount}
          sub={stats ? 'Human review queue' : 'Escalation required'}
          valueColor="#D97706"
          trend={stats ? `${stats.overview.rbi_reportable} RBI flagged` : '+5%'}
          trendUp={true}
        />
        <KpiCard
          icon={<CheckCircle2 size={18} />}
          label="Resolved"
          value={loading ? '…' : resolvedCount}
          sub={stats ? 'Closed & resolved' : 'Avg 4.2h resolution'}
          valueColor="#16A34A"
          trend={`${autoRate}% auto-resolved`}
          trendUp={false}
        />
      </div>

      {/* Daily volume chart (API only) */}
      {dailyVolume.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="font-semibold text-sm text-ub-blue flex items-center gap-2">
              <TrendingUp size={14} />
              Complaint Volume — Last 7 Days
            </div>
            <div className="text-xs text-gray-400">From live database</div>
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={dailyVolume} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#003087" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#003087" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10 }}
                tickLine={false}
                tickFormatter={(d) => d.slice(5)}
              />
              <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{ fontSize: 11, borderRadius: 8 }}
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

      {/* Category distribution (API only) */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {stats.distributions.by_category.slice(0, 6).map((cat, i) => {
            const colors = ['#003087', '#C8102E', '#0052CC', '#D97706', '#7C3AED', '#16A34A']
            return (
              <div key={cat.category} className="bg-white rounded-xl shadow-sm border border-gray-100 p-3 text-center">
                <div className="text-xl font-bold mb-0.5" style={{ color: colors[i % colors.length] }}>
                  {cat.count}
                </div>
                <div className="text-xs text-gray-500 leading-tight">{cat.category}</div>
                <div className="text-xs text-gray-400 mt-0.5">{cat.percent}%</div>
              </div>
            )
          })}
        </div>
      )}

      {/* Main content */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 md:gap-5">
        <div className="xl:col-span-2">
          <RecentComplaintsFeed complaints={COMPLAINTS.slice(0, 8)} setActive={setActive} />
        </div>
        <div className="flex flex-col gap-4">
          <ChannelBar stats={channelStats} />
          <AiMetrics
            autoRate={autoRate}
            rbiCount={stats?.overview.rbi_reportable}
            confidence={stats?.averages.avg_confidence_score}
          />
        </div>
      </div>
    </div>
  )
}

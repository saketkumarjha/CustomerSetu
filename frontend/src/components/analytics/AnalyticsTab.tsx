import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from 'recharts'
import { Clock, Bot, Star, ShieldAlert, RefreshCw, TrendingUp } from 'lucide-react'
import { TREND_DATA, CATEGORY_DATA, SENTIMENT_DATA, SLA_DATA, SENTIMENT_COLORS } from '../../data/analytics'
import { api } from '../../lib/api'
import { useApiData } from '../../hooks/useApiData'

const CATEGORY_COLORS = ['#003087', '#0052CC', '#C8102E', '#7C3AED', '#EA580C', '#0284C7', '#16A34A', '#D97706']

interface KpiProps { icon: React.ReactNode; label: string; value: string; color: string }
function AnalyticsKpi({ icon, label, value, color }: KpiProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 md:p-5">
      <div className="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center text-gray-400 mb-3">
        {icon}
      </div>
      <div className="text-2xl md:text-3xl font-bold mb-1" style={{ color }}>{value}</div>
      <div className="text-xs text-gray-500 leading-snug">{label}</div>
    </div>
  )
}

export function AnalyticsTab() {
  const { data: stats, loading: statsLoading, error: statsError, refetch } = useApiData(
    () => api.dashboard.stats(30),
    [],
  )

  const { data: csat } = useApiData(
    () => api.dashboard.csatTrends(30),
    [],
  )

  const { data: health } = useApiData(
    () => api.dashboard.pipelineHealth(7),
    [],
  )

  const usingApi = !!stats && !statsError

  // Build category chart data
  const categoryData = usingApi
    ? stats.distributions.by_category.slice(0, 8).map((c) => ({ name: c.category, count: c.count }))
    : CATEGORY_DATA

  // Build sentiment chart data
  const sentimentData = usingApi
    ? stats.distributions.by_sentiment.slice(0, 6).map((s) => ({
        name: s.sentiment,
        value: s.percent,
      }))
    : SENTIMENT_DATA

  // Build channel bar data
  const channelData = usingApi
    ? stats.distributions.by_channel.map((c) => ({ name: c.channel, value: c.count }))
    : []

  // CSAT trend for chart
  const csatTrend = csat?.weekly_trend?.filter((w) => w.avg_csat !== null) ?? []

  // KPI values
  const autoRate = usingApi ? `${stats.overview.auto_respond_rate_percent.toFixed(1)}%` : '38%'
  const rbiFlags = usingApi ? `${stats.overview.rbi_reportable}` : '12'
  const csatAvg = csat?.overall ? `${(csat.overall.average_csat / 5 * 100).toFixed(0)}%` : '87%'

  return (
    <div className="space-y-4 md:space-y-5">
      {/* Status */}
      <div className="flex items-center gap-3 flex-wrap">
        {usingApi && !statsLoading && (
          <span className="text-xs text-green-600 font-medium bg-green-50 px-2 py-0.5 rounded-full">● Live data</span>
        )}
        {statsError && (
          <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">Demo mode</span>
        )}
        <button onClick={refetch} className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 ml-auto">
          <RefreshCw size={10} /> Refresh
        </button>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <AnalyticsKpi icon={<Clock size={18} />} label="Avg Resolution Time" value={usingApi ? '~5 sec AI + 4h Human' : '4.2h'} color="#003087" />
        <AnalyticsKpi icon={<Bot size={18} />} label="AI Auto-Resolved" value={autoRate} color="#16A34A" />
        <AnalyticsKpi icon={<Star size={18} />} label={csat?.overall ? `CSAT (${csat.overall.total_responses} responses)` : 'Customer Satisfaction'} value={csatAvg} color="#D97706" />
        <AnalyticsKpi icon={<ShieldAlert size={18} />} label="RBI Regulatory Flags" value={rbiFlags} color="#C8102E" />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-5">
        {/* Trend or daily volume */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="font-semibold text-sm text-ub-blue mb-4 flex items-center gap-2">
            <TrendingUp size={14} />
            {usingApi ? 'Daily Complaint Volume (Last 7 Days)' : "Monthly Complaint Trend (Oct '25 – Mar '26)"}
          </div>
          <ResponsiveContainer width="100%" height={220}>
            {usingApi && stats.daily_volume.length > 0 ? (
              <AreaChart data={stats.daily_volume} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="blGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#003087" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#003087" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                <Area type="monotone" dataKey="count" stroke="#003087" fill="url(#blGrad)" strokeWidth={2} name="Complaints" />
              </AreaChart>
            ) : (
              <AreaChart data={TREND_DATA} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Area type="monotone" dataKey="total" stroke="#003087" fill="#EBF3FF" strokeWidth={2} name="Total" />
                <Area type="monotone" dataKey="resolved" stroke="#16A34A" fill="#D1FAE5" strokeWidth={2} name="Resolved" />
                <Area type="monotone" dataKey="critical" stroke="#C8102E" fill="#FEE2E2" strokeWidth={2} name="Critical" />
              </AreaChart>
            )}
          </ResponsiveContainer>
        </div>

        {/* Categories */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="font-semibold text-sm text-ub-blue mb-4">Complaints by Category</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={categoryData} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
              <XAxis type="number" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} tickLine={false} width={90} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]} name="Complaints">
                {categoryData.map((_, i) => (
                  <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-5">
        {/* Sentiment */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="font-semibold text-sm text-ub-blue mb-4">Customer Sentiment Distribution</div>
          <div className="flex items-center gap-6">
            <ResponsiveContainer width={180} height={180}>
              <PieChart>
                <Pie data={sentimentData} cx="50%" cy="50%" innerRadius={52} outerRadius={82} dataKey="value" paddingAngle={3}>
                  {sentimentData.map((_, i) => (
                    <Cell key={i} fill={SENTIMENT_COLORS[i % SENTIMENT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2 flex-1">
              {sentimentData.map((s, i) => (
                <div key={s.name} className="flex items-center gap-2 text-xs">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: SENTIMENT_COLORS[i % SENTIMENT_COLORS.length] }} />
                  <span className="text-gray-600 flex-1">{s.name}</span>
                  <span className="font-bold" style={{ color: SENTIMENT_COLORS[i % SENTIMENT_COLORS.length] }}>
                    {s.value}{typeof s.value === 'number' && s.value < 2 ? '' : '%'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* SLA or Channel */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="font-semibold text-sm text-ub-blue mb-4">
            {usingApi && channelData.length > 0 ? 'Complaints by Channel' : 'SLA Compliance Rate (%)'}
          </div>
          <ResponsiveContainer width="100%" height={180}>
            {usingApi && channelData.length > 0 ? (
              <BarChart data={channelData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]} name="Complaints">
                  {channelData.map((_, i) => (
                    <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            ) : (
              <BarChart data={SLA_DATA} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} domain={[0, 100]} />
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Bar dataKey="met" fill="#003087" stackId="a" name="Within SLA" />
                <Bar dataKey="breached" fill="#C8102E" stackId="a" name="SLA Breached" radius={[4, 4, 0, 0]} />
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>

      {/* CSAT weekly trend */}
      {csatTrend.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="font-semibold text-sm text-ub-blue mb-4">
            Weekly Customer Satisfaction Score (1–5 stars)
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={csatTrend} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
              <XAxis dataKey="week" tick={{ fontSize: 11 }} tickLine={false} />
              <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} domain={[1, 5]} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Area type="monotone" dataKey="avg_csat" stroke="#D97706" fill="#FEF3C7" strokeWidth={2} name="Avg CSAT" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Pipeline health */}
      {health?.per_agent && health.per_agent.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="font-semibold text-sm text-ub-blue mb-4 flex items-center gap-2">
            <Bot size={14} /> AI Agent Performance (Last 7 Days)
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[500px]">
              <thead>
                <tr className="text-gray-400 font-semibold uppercase tracking-wide border-b border-gray-100">
                  <th className="text-left pb-2 pr-3">Agent</th>
                  <th className="text-left pb-2 pr-3">Total Runs</th>
                  <th className="text-left pb-2 pr-3">Success Rate</th>
                  <th className="text-left pb-2">Avg Speed</th>
                </tr>
              </thead>
              <tbody>
                {health.per_agent.map((a) => (
                  <tr key={a.agent_name} className="border-b border-gray-50 last:border-0">
                    <td className="py-2 pr-3 font-medium text-gray-800">{a.agent_name}</td>
                    <td className="py-2 pr-3 text-gray-600">{a.total_runs}</td>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-100 rounded-full h-1.5 max-w-[60px]">
                          <div
                            className={`h-1.5 rounded-full ${a.success_rate >= 90 ? 'bg-green-500' : a.success_rate >= 70 ? 'bg-amber-500' : 'bg-red-500'}`}
                            style={{ width: `${a.success_rate}%` }}
                          />
                        </div>
                        <span className={`font-semibold ${a.success_rate >= 90 ? 'text-green-700' : 'text-amber-700'}`}>
                          {a.success_rate}%
                        </span>
                      </div>
                    </td>
                    <td className="py-2 text-gray-600">{a.avg_duration_ms ? `${a.avg_duration_ms}ms` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {health.summary && (
            <div className="flex gap-4 mt-4 pt-3 border-t border-gray-100 flex-wrap">
              <div className="text-xs text-gray-500">
                Total agent runs: <span className="font-bold text-gray-800">{health.summary.total_agent_executions}</span>
              </div>
              <div className="text-xs text-gray-500">
                Overall success: <span className="font-bold text-green-700">{health.summary.overall_success_rate}%</span>
              </div>
              <div className="text-xs text-gray-500">
                Failures: <span className="font-bold text-red-700">{health.summary.total_failures}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Confidence breakdown */}
      {usingApi && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="font-semibold text-sm text-ub-blue mb-4">Routing &amp; Confidence</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Auto-Resolved', value: stats.overview.auto_responded, color: '#16A34A', bg: 'bg-green-50' },
              { label: 'Human Review', value: stats.overview.human_review, color: '#D97706', bg: 'bg-amber-50' },
              { label: 'Avg AI Confidence', value: `${(stats.averages.avg_confidence_score * 100).toFixed(0)}%`, color: '#003087', bg: 'bg-blue-50' },
              { label: 'Avg Risk Score', value: `${(stats.averages.avg_risk_score * 100).toFixed(0)}%`, color: '#C8102E', bg: 'bg-red-50' },
            ].map((card) => (
              <div key={card.label} className={`${card.bg} rounded-xl p-3 text-center`}>
                <div className="text-xl font-bold mb-0.5" style={{ color: card.color }}>{card.value}</div>
                <div className="text-xs text-gray-500">{card.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

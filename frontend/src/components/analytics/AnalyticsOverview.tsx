import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp, ArrowUp, ArrowDown } from "lucide-react";
import { api } from "../../lib/api";
import { useApiData } from "../../hooks/useApiData";

interface MetricCardProps {
  label: string;
  value: string | number;
  trend?: number;
  subtitle?: string;
}

function MetricCard({ label, value, trend, subtitle }: MetricCardProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <span className="text-sm text-gray-500 font-medium">{label}</span>
        {trend !== undefined && (
          <div
            className={`flex items-center gap-1 text-xs font-semibold ${trend >= 0 ? "text-green-600" : "text-red-600"}`}
          >
            {trend >= 0 ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
            {Math.abs(trend)}%
          </div>
        )}
      </div>
      <div className="text-3xl font-bold text-gray-900 mb-1">{value}</div>
      {subtitle && <div className="text-xs text-gray-400">{subtitle}</div>}
    </div>
  );
}

export function AnalyticsOverview() {
  const {
    data: stats,
    loading,
    error,
  } = useApiData(() => api.dashboard.stats(7), []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading analytics...</div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Unable to load analytics data</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            Analytics Overview
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            7-day complaint analytics and insights
          </p>
        </div>
        <div className="text-xs text-gray-400">
          Generated:{" "}
          {new Date(stats.generated_at).toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Complaints"
          value={stats.overview.total_complaints}
          trend={0}
          subtitle="7-day period"
        />
        <MetricCard
          label="Auto-Responded"
          value={stats.overview.auto_responded}
          trend={stats.overview.auto_respond_rate_percent}
          subtitle={`${stats.overview.auto_respond_rate_percent.toFixed(1)}% auto response rate`}
        />
        <MetricCard
          label="RBI Reportable"
          value={stats.overview.rbi_reportable}
          trend={stats.overview.rbi_reportable_rate_percent}
          subtitle={`${stats.overview.rbi_reportable_rate_percent.toFixed(1)}% reportable rate`}
        />
        <MetricCard
          label="Avg Confidence"
          value={`${(stats.averages.avg_confidence_score * 100).toFixed(1)}%`}
          subtitle="pipeline confidence"
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Volume Chart */}
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <div className="flex items-center gap-2 mb-5">
            <TrendingUp size={16} className="text-gray-400" />
            <h3 className="font-semibold text-gray-900">Daily Volume</h3>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart
              data={stats.daily_volume}
              margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
            >
              <defs>
                <linearGradient id="volumeGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#f1f5f9"
                vertical={false}
              />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(d) =>
                  new Date(d).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })
                }
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  fontSize: 12,
                  borderRadius: 8,
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#6366f1"
                fill="url(#volumeGradient)"
                strokeWidth={2}
                name="Complaints"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Category Distribution */}
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-900 mb-5">
            Category Distribution
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart
              data={stats.distributions.by_category.slice(0, 6)}
              layout="vertical"
              margin={{ top: 10, right: 10, left: 10, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#f1f5f9"
                horizontal={false}
              />
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                dataKey="category"
                type="category"
                tick={{ fontSize: 10, fill: "#64748b" }}
                tickLine={false}
                axisLine={false}
                width={120}
              />
              <Tooltip
                contentStyle={{
                  fontSize: 12,
                  borderRadius: 8,
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                }}
              />
              <Bar
                dataKey="count"
                fill="#6366f1"
                radius={[0, 6, 6, 0]}
                name="Count"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Distribution Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Sentiment */}
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">
            Sentiment Distribution
          </h3>
          <div className="space-y-3">
            {stats.distributions.by_sentiment.slice(0, 5).map((item, idx) => (
              <div key={item.sentiment} className="flex items-center gap-3">
                <div
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{
                    backgroundColor: [
                      "#6366f1",
                      "#8b5cf6",
                      "#a855f7",
                      "#c084fc",
                      "#d8b4fe",
                    ][idx],
                  }}
                />
                <span className="text-sm text-gray-600 flex-1">
                  {item.sentiment}
                </span>
                <span className="text-sm font-semibold text-gray-900">
                  {item.count}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Severity */}
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Severity Levels</h3>
          <div className="space-y-3">
            {stats.distributions.by_severity
              .filter((s) => s.count > 0)
              .map((item) => (
                <div key={item.severity} className="flex items-center gap-3">
                  <div
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{
                      backgroundColor:
                        item.severity >= 4
                          ? "#ef4444"
                          : item.severity === 3
                            ? "#f59e0b"
                            : item.severity === 2
                              ? "#eab308"
                              : "#22c55e",
                    }}
                  />
                  <span className="text-sm text-gray-600 flex-1">
                    {item.label}
                  </span>
                  <span className="text-sm font-semibold text-gray-900">
                    {item.count}
                  </span>
                </div>
              ))}
          </div>
        </div>

        {/* Channel */}
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">
            Channel Breakdown
          </h3>
          <div className="space-y-3">
            {stats.distributions.by_channel.map((item, idx) => (
              <div key={item.channel} className="flex items-center gap-3">
                <div
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{
                    backgroundColor: ["#6366f1", "#8b5cf6", "#a855f7"][idx],
                  }}
                />
                <span className="text-sm text-gray-600 flex-1 capitalize">
                  {item.channel}
                </span>
                <span className="text-sm font-semibold text-gray-900">
                  {item.count}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

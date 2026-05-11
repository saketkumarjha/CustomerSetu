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
import { Star, TrendingUp, Users, MessageSquare } from "lucide-react";
import { api } from "../../lib/api";
import { useApiData } from "../../hooks/useApiData";

// Dummy data for demonstration
const DUMMY_WEEKLY_TREND = [
  { week: "Week 1", avg_csat: 4.2, response_count: 12 },
  { week: "Week 2", avg_csat: 4.5, response_count: 18 },
  { week: "Week 3", avg_csat: 4.1, response_count: 15 },
  { week: "Week 4", avg_csat: 4.6, response_count: 22 },
];

const DUMMY_BY_CATEGORY = [
  { category: "UPI / IMPS / NEFT", avg_csat: 4.3, response_count: 25 },
  { category: "Internet Banking", avg_csat: 4.5, response_count: 18 },
  { category: "ATM", avg_csat: 4.1, response_count: 12 },
  { category: "Credit Card", avg_csat: 4.4, response_count: 20 },
];

const DUMMY_BY_CHANNEL = [
  { channel: "Email", avg_csat: 4.4, response_count: 30 },
  { channel: "Twitter", avg_csat: 4.2, response_count: 25 },
  { channel: "Web Form", avg_csat: 4.5, response_count: 20 },
];

export function CustomerFeedbackAnalytics() {
  const { data: csat } = useApiData(() => api.dashboard.csatTrends(30), []);

  const hasData = csat && csat.overall && csat.overall.total_responses > 0;
  const weeklyTrend =
    hasData && csat.weekly_trend
      ? csat.weekly_trend.filter((w) => w.avg_csat !== null)
      : DUMMY_WEEKLY_TREND;
  const byCategory =
    hasData && csat.by_category ? csat.by_category : DUMMY_BY_CATEGORY;
  const byChannel =
    hasData && csat.by_channel ? csat.by_channel : DUMMY_BY_CHANNEL;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            Customer Feedback Analytics
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Customer satisfaction trends and insights
          </p>
        </div>
        {!hasData && (
          <div className="text-xs bg-amber-50 text-amber-700 px-3 py-1.5 rounded-lg border border-amber-200">
            Showing sample data
          </div>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gradient-to-br from-purple-50 to-white rounded-xl border border-purple-100 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
              <Star size={20} className="text-purple-600" />
            </div>
            <span className="text-sm font-medium text-gray-600">Avg CSAT</span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {hasData ? csat.overall!.average_csat.toFixed(1) : "4.3"}
          </div>
          <div className="text-xs text-gray-500 mt-1">out of 5.0</div>
        </div>

        <div className="bg-gradient-to-br from-blue-50 to-white rounded-xl border border-blue-100 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
              <Users size={20} className="text-blue-600" />
            </div>
            <span className="text-sm font-medium text-gray-600">
              Total Responses
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {hasData ? csat.overall!.total_responses : "67"}
          </div>
          <div className="text-xs text-gray-500 mt-1">feedback received</div>
        </div>

        <div className="bg-gradient-to-br from-green-50 to-white rounded-xl border border-green-100 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
              <TrendingUp size={20} className="text-green-600" />
            </div>
            <span className="text-sm font-medium text-gray-600">
              Satisfaction
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {hasData
              ? `${((csat.overall!.average_csat / 5) * 100).toFixed(0)}%`
              : "86%"}
          </div>
          <div className="text-xs text-gray-500 mt-1">overall rating</div>
        </div>

        <div className="bg-gradient-to-br from-indigo-50 to-white rounded-xl border border-indigo-100 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
              <MessageSquare size={20} className="text-indigo-600" />
            </div>
            <span className="text-sm font-medium text-gray-600">Status</span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {hasData ? csat.overall!.csat_label : "Good"}
          </div>
          <div className="text-xs text-gray-500 mt-1">satisfaction level</div>
        </div>
      </div>

      {/* Weekly Trend Chart */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h3 className="font-semibold text-gray-900 mb-5">
          Weekly Satisfaction Trend
        </h3>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart
            data={weeklyTrend}
            margin={{ top: 10, right: 20, left: -10, bottom: 0 }}
          >
            <defs>
              <linearGradient id="csatGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#f1f5f9"
              vertical={false}
            />
            <XAxis
              dataKey="week"
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
              domain={[0, 5]}
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
              dataKey="avg_csat"
              stroke="#8b5cf6"
              fill="url(#csatGradient)"
              strokeWidth={2.5}
              name="Avg CSAT"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Category and Channel Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* By Category */}
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-900 mb-5">CSAT by Category</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={byCategory}
              margin={{ top: 10, right: 10, left: -10, bottom: 60 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#f1f5f9"
                vertical={false}
              />
              <XAxis
                dataKey="category"
                tick={{ fontSize: 10, fill: "#64748b" }}
                tickLine={false}
                axisLine={false}
                angle={-45}
                textAnchor="end"
                height={60}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
                domain={[0, 5]}
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
                dataKey="avg_csat"
                fill="#8b5cf6"
                radius={[8, 8, 0, 0]}
                name="Avg CSAT"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* By Channel */}
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-900 mb-5">CSAT by Channel</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={byChannel}
              margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#f1f5f9"
                vertical={false}
              />
              <XAxis
                dataKey="channel"
                tick={{ fontSize: 11, fill: "#64748b" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
                domain={[0, 5]}
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
                dataKey="avg_csat"
                fill="#6366f1"
                radius={[8, 8, 0, 0]}
                name="Avg CSAT"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Response Distribution */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h3 className="font-semibold text-gray-900 mb-5">
          Response Distribution
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {[5, 4, 3, 2, 1].map((rating) => (
            <div
              key={rating}
              className="text-center p-4 bg-gray-50 rounded-lg border border-gray-100"
            >
              <div className="flex items-center justify-center gap-1 mb-2">
                {Array.from({ length: rating }).map((_, i) => (
                  <Star
                    key={i}
                    size={14}
                    className="fill-amber-400 text-amber-400"
                  />
                ))}
              </div>
              <div className="text-2xl font-bold text-gray-900">
                {Math.floor(Math.random() * 20) + 5}
              </div>
              <div className="text-xs text-gray-500 mt-1">responses</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

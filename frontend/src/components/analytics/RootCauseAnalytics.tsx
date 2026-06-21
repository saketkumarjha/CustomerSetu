import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { AlertTriangle, TrendingDown, FileText, Lightbulb } from "lucide-react";
import { api } from "../../lib/api";
import { useApiData } from "../../hooks/useApiData";
import { useState } from "react";

const COLORS = ["#ef4444", "#f59e0b", "#eab308", "#84cc16", "#22c55e"];

export function RootCauseAnalytics() {
  const [minRating, setMinRating] = useState(5);
  const [limit, setLimit] = useState(10);

  const {
    data: rootCause,
    loading,
    error,
    refetch,
  } = useApiData(
    () => api.dashboard.rootCause({ min_rating: minRating, limit }),
    [minRating, limit],
  );

  const hasData = rootCause && rootCause.total_analysed > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            Root-Cause Analysis
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            AI-powered analysis of low-rated complaints
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-600 font-medium">
              Min Rating:
            </label>
            <select
              value={minRating}
              onChange={(e) => setMinRating(Number(e.target.value))}
              className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value={1}>≤ 1 star (critical)</option>
              <option value={2}>≤ 2 stars (poor)</option>
              <option value={3}>≤ 3 stars (neutral)</option>
              <option value={4}>≤ 4 stars</option>
              <option value={5}>All ratings</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-600 font-medium">Limit:</label>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>
          <button
            onClick={() => refetch()}
            className="text-xs bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Analyze
          </button>
        </div>
      </div>

      {/* Status Message */}
      {loading && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 text-center">
          <div className="text-blue-600 font-medium">
            Analyzing complaints...
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <div className="text-red-600 font-medium">Error loading analysis</div>
        </div>
      )}

      {!loading && !error && rootCause?.message && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle
              size={20}
              className="text-blue-600 flex-shrink-0 mt-0.5"
            />
            <div>
              <div className="font-semibold text-blue-900 mb-1">Demo Data</div>
              <div className="text-sm text-blue-700">{rootCause.message}</div>
            </div>
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {hasData && (
        <>
          {/* Summary Card */}
          <div className="bg-gradient-to-br from-red-50 to-white rounded-xl border border-red-100 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-lg bg-red-100 flex items-center justify-center">
                <TrendingDown size={24} className="text-red-600" />
              </div>
              <div>
                <div className="text-sm text-gray-600 font-medium">
                  Total Analyzed
                </div>
                <div className="text-3xl font-bold text-gray-900">
                  {rootCause.total_analysed}
                </div>
              </div>
            </div>
            <div className="text-sm text-gray-600">
              Low-rated complaints analyzed for common patterns and root causes
            </div>
          </div>

          {/* Common Themes */}
          {rootCause.common_themes && rootCause.common_themes.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 p-6">
              <div className="flex items-center gap-2 mb-5">
                <FileText size={18} className="text-gray-400" />
                <h3 className="font-semibold text-gray-900">Common Themes</h3>
              </div>
              <div className="space-y-4">
                {rootCause.common_themes.map((theme, idx) => (
                  <div
                    key={idx}
                    className="border border-gray-100 rounded-lg p-4 hover:shadow-sm transition-shadow"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <div className="font-semibold text-gray-900 mb-1">
                          {theme.theme}
                        </div>
                        <div className="text-xs text-gray-500">
                          Found in {theme.frequency} complaint
                          {theme.frequency > 1 ? "s" : ""}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-red-500 h-2 rounded-full"
                            style={{
                              width: `${(theme.frequency / rootCause.total_analysed) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs font-semibold text-gray-600 min-w-[35px]">
                          {Math.round(
                            (theme.frequency / rootCause.total_analysed) * 100,
                          )}
                          %
                        </span>
                      </div>
                    </div>
                    {theme.example_complaints &&
                      theme.example_complaints.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-gray-100">
                          <div className="text-xs text-gray-500 mb-2">
                            Example complaints:
                          </div>
                          <div className="space-y-1">
                            {theme.example_complaints
                              .slice(0, 2)
                              .map((example, i) => (
                                <div
                                  key={i}
                                  className="text-xs text-gray-600 bg-gray-50 rounded px-2 py-1"
                                >
                                  {example}
                                </div>
                              ))}
                          </div>
                        </div>
                      )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Category Breakdown */}
            {rootCause.category_breakdown &&
              Object.keys(rootCause.category_breakdown).length > 0 && (
                <div className="bg-white rounded-xl border border-gray-100 p-6">
                  <h3 className="font-semibold text-gray-900 mb-5">
                    Category Breakdown
                  </h3>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart
                      data={Object.entries(rootCause.category_breakdown).map(
                        ([category, count]) => ({
                          category,
                          count,
                        }),
                      )}
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
                        fill="#ef4444"
                        radius={[8, 8, 0, 0]}
                        name="Count"
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

            {/* Sentiment Patterns */}
            {rootCause.sentiment_patterns &&
              Object.keys(rootCause.sentiment_patterns).length > 0 && (
                <div className="bg-white rounded-xl border border-gray-100 p-6">
                  <h3 className="font-semibold text-gray-900 mb-5">
                    Sentiment Patterns
                  </h3>
                  <div className="flex items-center justify-center">
                    <ResponsiveContainer width="100%" height={280}>
                      <PieChart>
                        <Pie
                          data={Object.entries(
                            rootCause.sentiment_patterns,
                          ).map(([sentiment, count]) => ({
                            name: sentiment,
                            value: count,
                          }))}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={100}
                          paddingAngle={3}
                          dataKey="value"
                        >
                          {Object.keys(rootCause.sentiment_patterns).map(
                            (_, index) => (
                              <Cell
                                key={`cell-${index}`}
                                fill={COLORS[index % COLORS.length]}
                              />
                            ),
                          )}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            fontSize: 12,
                            borderRadius: 8,
                            border: "1px solid #e2e8f0",
                            boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                          }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-4 space-y-2">
                    {Object.entries(rootCause.sentiment_patterns).map(
                      ([sentiment, count], idx) => (
                        <div
                          key={sentiment}
                          className="flex items-center gap-2 text-xs"
                        >
                          <div
                            className="w-3 h-3 rounded-full flex-shrink-0"
                            style={{
                              backgroundColor: COLORS[idx % COLORS.length],
                            }}
                          />
                          <span className="text-gray-600 flex-1">
                            {sentiment}
                          </span>
                          <span className="font-semibold text-gray-900">
                            {count}
                          </span>
                        </div>
                      ),
                    )}
                  </div>
                </div>
              )}
          </div>

          {/* Recommendations */}
          {rootCause.recommendations &&
            rootCause.recommendations.length > 0 && (
              <div className="bg-gradient-to-br from-indigo-50 to-white rounded-xl border border-indigo-100 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Lightbulb size={18} className="text-indigo-600" />
                  <h3 className="font-semibold text-gray-900">
                    AI Recommendations
                  </h3>
                </div>
                <div className="space-y-3">
                  {rootCause.recommendations.map((rec, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-3 bg-white rounded-lg p-4 border border-indigo-100"
                    >
                      <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span className="text-xs font-bold text-indigo-600">
                          {idx + 1}
                        </span>
                      </div>
                      <div className="text-sm text-gray-700 flex-1">{rec}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
        </>
      )}
    </div>
  );
}

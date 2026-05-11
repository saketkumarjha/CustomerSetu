import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Bot, Zap, CheckCircle2, AlertCircle } from "lucide-react";
import { api } from "../../lib/api";
import { useApiData } from "../../hooks/useApiData";

export function AIPerformanceAnalytics() {
  const {
    data: health,
    loading,
    error,
  } = useApiData(() => api.dashboard.pipelineHealth(7), []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading AI performance data...</div>
      </div>
    );
  }

  if (error || !health || !health.per_agent) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Unable to load AI performance data</div>
      </div>
    );
  }

  const chartData = health.per_agent.map((agent) => ({
    name: agent.agent_name.replace(" Agent", "").replace("Agent", "").trim(),
    success_rate: agent.success_rate,
    avg_duration: agent.avg_duration_ms,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            AI Performance Analytics
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Pipeline agent metrics and performance insights
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gradient-to-br from-indigo-50 to-white rounded-xl border border-indigo-100 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
              <Bot size={20} className="text-indigo-600" />
            </div>
            <span className="text-sm font-medium text-gray-600">
              Total Agents
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {health.per_agent.length}
          </div>
        </div>

        <div className="bg-gradient-to-br from-green-50 to-white rounded-xl border border-green-100 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
              <CheckCircle2 size={20} className="text-green-600" />
            </div>
            <span className="text-sm font-medium text-gray-600">
              Success Rate
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {health.summary?.overall_success_rate}%
          </div>
        </div>

        <div className="bg-gradient-to-br from-blue-50 to-white rounded-xl border border-blue-100 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
              <Zap size={20} className="text-blue-600" />
            </div>
            <span className="text-sm font-medium text-gray-600">
              Total Executions
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {health.summary?.total_agent_executions}
          </div>
        </div>

        <div className="bg-gradient-to-br from-red-50 to-white rounded-xl border border-red-100 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
              <AlertCircle size={20} className="text-red-600" />
            </div>
            <span className="text-sm font-medium text-gray-600">
              Total Failures
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {health.summary?.total_failures}
          </div>
        </div>
      </div>

      {/* Success Rate Chart */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h3 className="font-semibold text-gray-900 mb-5">
          Agent Success Rates
        </h3>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart
            data={chartData}
            margin={{ top: 10, right: 20, left: 20, bottom: 80 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#f1f5f9"
              vertical={false}
            />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 10, fill: "#64748b" }}
              tickLine={false}
              axisLine={false}
              angle={-45}
              textAnchor="end"
              height={80}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
              domain={[0, 100]}
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
              dataKey="success_rate"
              radius={[8, 8, 0, 0]}
              name="Success Rate (%)"
            >
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={
                    entry.success_rate === 100
                      ? "#22c55e"
                      : entry.success_rate >= 95
                        ? "#6366f1"
                        : "#f59e0b"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Agent Performance Table */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h3 className="font-semibold text-gray-900 mb-5">
          Detailed Agent Metrics
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Agent Name
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Order
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Total Runs
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Success Rate
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Failures
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Avg Duration
                </th>
              </tr>
            </thead>
            <tbody>
              {health.per_agent.map((agent, idx) => (
                <tr
                  key={agent.agent_name}
                  className={`border-b border-gray-50 ${idx % 2 === 0 ? "bg-gray-50/50" : ""}`}
                >
                  <td className="py-3 px-4 text-sm font-medium text-gray-900">
                    {agent.agent_name}
                  </td>
                  <td className="py-3 px-4 text-sm text-gray-600">
                    {agent.agent_order}
                  </td>
                  <td className="py-3 px-4 text-sm text-gray-600">
                    {agent.total_runs}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-gray-100 rounded-full h-2 max-w-[80px]">
                        <div
                          className={`h-2 rounded-full ${
                            agent.success_rate === 100
                              ? "bg-green-500"
                              : agent.success_rate >= 95
                                ? "bg-indigo-500"
                                : "bg-amber-500"
                          }`}
                          style={{ width: `${agent.success_rate}%` }}
                        />
                      </div>
                      <span className="text-sm font-semibold text-gray-900 min-w-[45px]">
                        {agent.success_rate}%
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-sm text-gray-600">
                    {agent.failure_count}
                  </td>
                  <td className="py-3 px-4 text-sm text-gray-600">
                    {agent.avg_duration_ms ? `${agent.avg_duration_ms}ms` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

import {
  RefreshCw,
  Clock,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Users,
} from "lucide-react";
import { api } from "../../lib/api";
import { useApiData } from "../../hooks/useApiData";

function RiskBadge({ level }: { level: string }) {
  const map: Record<string, string> = {
    CRITICAL: "bg-red-100 text-red-800 border-red-200",
    HIGH: "bg-orange-100 text-orange-800 border-orange-200",
    MODERATE: "bg-amber-100 text-amber-800 border-amber-200",
    LOW: "bg-green-100 text-green-700 border-green-200",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-bold border ${map[level] ?? "bg-gray-100 text-gray-700 border-gray-200"}`}
    >
      {level}
    </span>
  );
}

export function SLATab() {
  const {
    data: summary,
    loading: summaryLoading,
    refetch: refetchSummary,
  } = useApiData(() => api.sla.summary(), []);

  const {
    data: atRisk,
    loading: atRiskLoading,
    refetch: refetchAtRisk,
  } = useApiData(() => api.sla.atRisk(), []);

  const refetch = () => {
    refetchSummary();
    refetchAtRisk();
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center">
            <Clock size={20} className="text-amber-600" />
          </div>
          <div>
            <h1 className="text-base font-bold text-gray-800">SLA Tracker</h1>
            <p className="text-xs text-gray-500">
              Monitor complaint deadlines and get early warnings before they
              breach
            </p>
          </div>
        </div>
        <button
          onClick={refetch}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50"
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {summaryLoading && (
        <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center text-sm text-gray-400">
          Loading SLA data…
        </div>
      )}

      {summary && (
        <>
          {/* System health banner */}
          {summary.action_required && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
              <AlertTriangle
                size={18}
                className="text-red-600 flex-shrink-0 mt-0.5"
              />
              <div>
                <p className="text-sm font-bold text-red-800">
                  Immediate Action Required
                </p>
                <p className="text-xs text-red-600 mt-0.5">
                  {summary.predicted_breach.critical > 0 &&
                    `${summary.predicted_breach.critical} complaint(s) will breach SLA imminently. `}
                  {summary.rbi_tat_breached > 0 &&
                    `${summary.rbi_tat_breached} RBI TAT deadline(s) have been breached.`}
                </p>
              </div>
            </div>
          )}

          {!summary.action_required && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3">
              <CheckCircle2
                size={18}
                className="text-green-600 flex-shrink-0"
              />
              <p className="text-sm text-green-700 font-medium">
                All SLA deadlines are on track. No immediate action needed.
              </p>
            </div>
          )}

          {/* Summary stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              {
                icon: <Users size={16} />,
                label: "Open Complaints",
                value: summary.open_complaints,
                color: "text-ub-blue",
                bg: "bg-blue-50",
              },
              {
                icon: <Clock size={16} />,
                label: "Awaiting Review",
                value: summary.human_review_queue,
                color: "text-amber-700",
                bg: "bg-amber-50",
              },
              {
                icon: <AlertTriangle size={16} />,
                label: "RBI TAT Breached",
                value: summary.rbi_tat_breached,
                color:
                  summary.rbi_tat_breached > 0
                    ? "text-red-700"
                    : "text-green-700",
                bg: summary.rbi_tat_breached > 0 ? "bg-red-50" : "bg-green-50",
              },
              {
                icon: <TrendingUp size={16} />,
                label: "At Risk (24h)",
                value: summary.predicted_breach.total_at_risk,
                color:
                  summary.predicted_breach.total_at_risk > 0
                    ? "text-orange-700"
                    : "text-green-700",
                bg:
                  summary.predicted_breach.total_at_risk > 0
                    ? "bg-orange-50"
                    : "bg-green-50",
              },
            ].map((card) => (
              <div key={card.label} className={`${card.bg} rounded-xl p-4`}>
                <div className={`flex items-center gap-1.5 mb-2 ${card.color}`}>
                  {card.icon}
                </div>
                <div className={`text-2xl font-bold mb-0.5 ${card.color}`}>
                  {card.value}
                </div>
                <div className="text-xs text-gray-500">{card.label}</div>
              </div>
            ))}
          </div>

          {/* Breach prediction breakdown */}
          {summary.predicted_breach.total_at_risk > 0 && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <h2 className="text-sm font-bold text-gray-700 mb-3">
                Predicted Breach Risk (Next Few Hours)
              </h2>
              <div className="flex flex-wrap gap-3">
                <div className="flex items-center gap-2 bg-red-50 rounded-xl px-4 py-3">
                  <span className="text-2xl font-bold text-red-700">
                    {summary.predicted_breach.critical}
                  </span>
                  <div>
                    <div className="text-xs font-bold text-red-700">
                      CRITICAL
                    </div>
                    <div className="text-xs text-gray-500">
                      Will breach very soon
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 bg-orange-50 rounded-xl px-4 py-3">
                  <span className="text-2xl font-bold text-orange-700">
                    {summary.predicted_breach.high}
                  </span>
                  <div>
                    <div className="text-xs font-bold text-orange-700">
                      HIGH RISK
                    </div>
                    <div className="text-xs text-gray-500">
                      Needs attention today
                    </div>
                  </div>
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-3">
                Our AI predicts breach risk 2–6 hours before they happen based
                on complaint type, severity, and queue depth.
              </p>
            </div>
          )}
        </>
      )}

      {/* At-risk list */}
      {!atRiskLoading && atRisk && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} className="text-amber-600" />
              <h2 className="text-sm font-bold text-gray-700">
                At-Risk Complaints
              </h2>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {Object.entries(atRisk.risk_summary ?? {}).map(
                ([level, count]) =>
                  count > 0 && (
                    <div key={level} className="flex items-center gap-1">
                      <RiskBadge level={level} />
                      <span className="text-xs text-gray-500">{count}</span>
                    </div>
                  ),
              )}
            </div>
          </div>

          {atRisk.system_alert && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-xs text-red-700">
              {atRisk.system_alert}
            </div>
          )}

          {(atRisk.predictions ?? []).length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 rounded-xl p-4">
              <CheckCircle2 size={16} />
              No complaints are at risk of breaching SLA right now.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[550px]">
                <thead>
                  <tr className="text-xs text-gray-400 font-semibold uppercase tracking-wide border-b border-gray-100">
                    <th className="text-left pb-2 pr-3">Complaint ID</th>
                    <th className="text-left pb-2 pr-3">Category</th>
                    <th className="text-left pb-2 pr-3">Risk Level</th>
                    <th className="text-left pb-2 pr-3">Breach Probability</th>
                    <th className="text-left pb-2">Time to Breach</th>
                  </tr>
                </thead>
                <tbody>
                  {(atRisk.predictions ?? []).map((p) => (
                    <tr
                      key={p.complaint_id}
                      className="border-b border-gray-50 last:border-0"
                    >
                      <td className="py-2.5 pr-3 font-mono text-xs font-semibold text-ub-blue">
                        {p.complaint_id}
                      </td>
                      <td className="py-2.5 pr-3 text-xs text-gray-700">
                        {p.category ?? "—"}
                      </td>
                      <td className="py-2.5 pr-3">
                        <RiskBadge level={p.risk_level} />
                      </td>
                      <td className="py-2.5 pr-3">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-gray-100 rounded-full h-1.5 max-w-[80px]">
                            <div
                              className={`h-1.5 rounded-full ${p.risk_level === "CRITICAL" ? "bg-red-500" : p.risk_level === "HIGH" ? "bg-orange-500" : "bg-amber-400"}`}
                              style={{
                                width: `${Math.round(p.breach_probability * 100)}%`,
                              }}
                            />
                          </div>
                          <span className="text-xs font-semibold text-gray-700">
                            {Math.round(p.breach_probability * 100)}%
                          </span>
                        </div>
                      </td>
                      <td className="py-2.5 text-xs text-gray-500">
                        {p.estimated_breach_in_hours !== undefined ? (
                          p.estimated_breach_in_hours < 0 ? (
                            <span className="text-red-600 font-semibold">
                              Breached
                            </span>
                          ) : (
                            `~${Math.round(p.estimated_breach_in_hours)}h`
                          )
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* How it works */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
        <p className="text-xs font-bold text-ub-blue mb-2">
          How does SLA prediction work?
        </p>
        <p className="text-xs text-gray-600 leading-relaxed">
          Our AI analyses 6 signals to predict SLA breaches before they happen:
          time elapsed (35%), current queue pressure (20%), complaint severity
          (15%), time of day (10%), day of week (10%), and historical resolution
          times (10%). Predictions are refreshed every few minutes.
        </p>
      </div>
    </div>
  );
}

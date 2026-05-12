import { ArrowRight } from "lucide-react";
import type { TabId } from "../../types";
import type { ApiComplaint } from "../../lib/api";
import { StatusBadge } from "../ui/StatusBadge";
import { ChannelBadge } from "../ui/ChannelBadge";
import { SlaBadge } from "../ui/SlaBadge";
import { statusFromApi, slaLabel, isSlaBreached } from "../../types";

interface Props {
  complaints: ApiComplaint[];
  loading?: boolean;
  setActive: (id: TabId) => void;
}

const HEADERS = ["ID", "Customer", "Channel", "Category", "Status", "SLA"];

export function RecentComplaintsFeed({
  complaints,
  loading,
  setActive,
}: Props) {
  return (
    <div className="glass-panel overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100 flex-shrink-0">
        <div className="text-xs font-semibold text-slate-800">
          Recent Complaints
        </div>
        <button
          type="button"
          onClick={() => setActive("complaints")}
          className="flex items-center gap-1 text-xs font-semibold text-ub-blue hover:underline"
        >
          View All <ArrowRight size={11} />
        </button>
      </div>

      {/* Table */}
      <div className="overflow-auto flex-1">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 border-b border-gray-100">
            <tr>
              {HEADERS.map((h) => (
                <th
                  key={h}
                  className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td
                  colSpan={HEADERS.length}
                  className="px-4 py-8 text-center text-xs text-slate-400"
                >
                  Loading…
                </td>
              </tr>
            )}

            {!loading && complaints.length === 0 && (
              <tr>
                <td
                  colSpan={HEADERS.length}
                  className="px-4 py-8 text-center text-xs text-slate-400"
                >
                  No recent complaints
                </td>
              </tr>
            )}

            {!loading &&
              complaints.map((c) => {
                const pipelineDone = c.pipeline_status === "complete";
                const stat = statusFromApi(c.status, c.route);
                const category =
                  pipelineDone && c.category
                    ? c.category
                    : pipelineDone
                      ? "General"
                      : "Analysing…";
                const hasSlaData = !!(
                  c.rbi_tat_deadline ||
                  c.sla_hours ||
                  c.created_at
                );
                const slaLbl = hasSlaData
                  ? slaLabel(c.sla_hours, c.created_at, c.rbi_tat_deadline)
                  : "—";
                const breached = hasSlaData
                  ? isSlaBreached(c.sla_hours, c.created_at, c.rbi_tat_deadline)
                  : false;
                const channel =
                  (c.channel as import("../../types").Channel) ?? "Email";

                return (
                  <tr
                    key={c.complaint_id}
                    className="border-b border-gray-50 hover:bg-slate-50 transition-colors last:border-0"
                  >
                    {/* ID */}
                    <td className="px-4 py-3 text-xs font-mono font-semibold text-ub-blue whitespace-nowrap">
                      {c.complaint_id}
                    </td>

                    {/* Customer */}
                    <td className="px-4 py-3">
                      <div className="font-semibold text-gray-800 whitespace-nowrap text-xs">
                        {c.customer_id}
                      </div>
                    </td>

                    {/* Channel */}
                    <td className="px-4 py-3">
                      <ChannelBadge channel={channel} />
                    </td>

                    {/* Category */}
                    <td className="px-4 py-3">
                      <div
                        className={`text-xs whitespace-nowrap ${!pipelineDone ? "text-slate-400 italic" : "text-gray-800"}`}
                      >
                        {category}
                      </div>
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3">
                      <StatusBadge status={stat} />
                    </td>

                    {/* SLA */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <SlaBadge breached={breached} label={slaLbl} />
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

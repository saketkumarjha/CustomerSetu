import type { CustomerCard as CustomerCardType } from "../../types";
import { getInitials } from "../../utils/styles";

interface Props {
  customer: CustomerCardType;
  onClick: () => void;
}

function StatChip({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex flex-col items-center px-2 py-1 rounded-md bg-slate-50 border border-slate-100 min-w-[48px]">
      <span className={`text-sm font-bold ${color}`}>{value}</span>
      <span className="text-[10px] text-slate-400 leading-tight">{label}</span>
    </div>
  );
}

export function CustomerCard({ customer, onClick }: Props) {
  const initials = getInitials(customer.name || "?");
  const hasActive = customer.active_complaints > 0;

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full text-left bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md hover:border-ub-blue/30 transition-all p-4 space-y-3 group"
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="relative flex-shrink-0">
          <div className="w-10 h-10 rounded-full bg-ub-blue text-white flex items-center justify-center text-sm font-bold">
            {initials}
          </div>
          {hasActive && (
            <span className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 border-2 border-white" title="Has active complaints" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800 truncate group-hover:text-ub-blue transition-colors">
            {customer.name}
          </p>
          <p className="text-xs text-slate-400 font-mono truncate">{customer.cif_id}</p>
        </div>
        {customer.verified && (
          <span className="flex-shrink-0 text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.5 rounded font-medium">
            Verified
          </span>
        )}
      </div>

      {/* Contact */}
      <div className="space-y-0.5">
        {customer.email && (
          <p className="text-xs text-slate-500 truncate">{customer.email}</p>
        )}
        {customer.phone && (
          <p className="text-xs text-slate-400 truncate">{customer.phone}</p>
        )}
      </div>

      {/* Stats chips */}
      <div className="flex gap-1.5 flex-wrap">
        <StatChip label="Total" value={customer.total_complaints} color="text-slate-700" />
        <StatChip label="Active" value={customer.active_complaints} color="text-amber-600" />
        <StatChip label="Resolved" value={customer.resolved_complaints} color="text-emerald-600" />
        <StatChip label="Merged" value={customer.merged_complaints} color="text-slate-400" />
      </div>

      {/* Last complaint */}
      {customer.last_complaint_date && (
        <div className="flex items-center justify-between pt-1 border-t border-slate-100">
          <span className="text-[11px] text-slate-400">
            Last: {customer.last_complaint_date}
          </span>
          {customer.last_complaint_status && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
              {customer.last_complaint_status}
            </span>
          )}
        </div>
      )}
    </button>
  );
}

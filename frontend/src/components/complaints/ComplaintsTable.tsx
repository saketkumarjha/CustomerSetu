import { useState, Fragment } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { Complaint } from "../../types";
import { StatusBadge } from "../ui/StatusBadge";
import { ChannelBadge } from "../ui/ChannelBadge";
import { SlaBadge } from "../ui/SlaBadge";
import { CustomerSummaryCard } from "../customers/CustomerSummaryCard";

interface Props {
  complaints: Complaint[];
  selected: Complaint | null;
  onSelect: (c: Complaint) => void;
  mergedChildrenMap?: Map<string, Complaint[]>;
  loading?: boolean;
  cifIdMap?: Map<string, string>;
}

const HEADERS = [
  "",        // chevron column
  "ID",
  "Customer",
  "Channel",
  "Category / Type",
  "Status",
  "SLA",
  "History",
  "",        // duplicate flag / actions
];

interface MergedChildrenPanelProps {
  mergedItems: Complaint[];
  isExpanded: boolean;
  onSelect: (c: Complaint) => void;
}

function MergedChildrenPanel({ mergedItems, isExpanded, onSelect }: MergedChildrenPanelProps) {
  return (
    <div
      className={`overflow-hidden transition-[max-height] duration-200 ease-in-out ${
        isExpanded ? "max-h-[600px]" : "max-h-0"
      }`}
    >
      <div className="bg-slate-50 border-t border-slate-200 px-4 pt-3 pb-4">
        {/* Header */}
        <div className="flex items-center gap-2 mb-3">
          <svg
            className="text-indigo-400"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <span className="text-xs font-semibold text-slate-700">
            Merged Complaints ({mergedItems.length})
          </span>
          <span className="text-xs text-gray-400">
            These complaints have been merged into the parent complaint above.
          </span>
        </div>

        {/* Child rows */}
        <div className="border-l-2 border-indigo-200 pl-3 space-y-1">
          {mergedItems.map((child, idx) => {
            const isLast = idx === mergedItems.length - 1;
            return (
              <div
                key={child.id}
                className="flex items-center gap-3 py-2 border-b border-slate-100 last:border-0"
              >
                {/* Tree indicator */}
                <span className="font-mono text-xs text-gray-300 select-none flex-shrink-0">
                  {isLast ? "└──" : "├──"}
                </span>

                {/* ID — clickable */}
                <button
                  onClick={() => onSelect(child)}
                  className="text-xs font-mono font-semibold text-ub-blue hover:underline whitespace-nowrap flex-shrink-0"
                >
                  {child.id}
                </button>

                {/* Customer */}
                <span className="text-xs text-gray-700 whitespace-nowrap flex-shrink-0 min-w-[140px]">
                  {child.customer}
                </span>

                {/* Channel */}
                <span className="flex-shrink-0">
                  <ChannelBadge channel={child.channel} />
                </span>

                {/* Category */}
                <span className="text-xs text-gray-600 flex-1 min-w-0 truncate">
                  {child.category}
                </span>

                {/* Status + Merged pill */}
                <span className="flex items-center gap-1 flex-shrink-0">
                  <StatusBadge status="Resolved" />
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-500 font-medium">
                    Merged
                  </span>
                </span>

                {/* Filed */}
                <span className="text-xs text-gray-400 whitespace-nowrap flex-shrink-0">
                  {child.date} {child.time}
                </span>

                {/* Actions */}
                <button
                  onClick={() => onSelect(child)}
                  className="flex-shrink-0 p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-slate-100"
                  title="Open complaint"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
                  </svg>
                </button>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <p className="mt-2 text-xs text-gray-400">
          {mergedItems.length} complaint{mergedItems.length !== 1 ? "s" : ""} merged into this parent
        </p>
      </div>
    </div>
  );
}

export function ComplaintsTable({ complaints, selected, onSelect, mergedChildrenMap = new Map(), loading = false, cifIdMap }: Props) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleExpand = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="glass-panel overflow-hidden flex-1 flex flex-col min-h-0">
      <div className="overflow-auto flex-1">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 border-b border-gray-100">
            <tr>
              {HEADERS.map((h, i) => (
                <th
                  key={i}
                  className={`text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap ${i === 0 ? "w-8 px-2" : ""}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 6 }).map((_, i) => (
              <tr key={i} className="border-b border-gray-50">
                <td className="w-8 px-2 py-3"><div className="w-4 h-3 bg-gray-200 rounded animate-pulse" /></td>
                <td className="px-4 py-3"><div className="w-28 h-3 bg-gray-200 rounded animate-pulse" /></td>
                <td className="px-4 py-3"><div className="w-24 h-3 bg-gray-200 rounded animate-pulse" /></td>
                <td className="px-4 py-3"><div className="w-16 h-5 bg-gray-200 rounded animate-pulse" /></td>
                <td className="px-4 py-3"><div className="w-32 h-3 bg-gray-200 rounded animate-pulse" /></td>
                <td className="px-4 py-3"><div className="w-16 h-5 bg-gray-200 rounded animate-pulse" /></td>
                <td className="px-4 py-3"><div className="w-20 h-3 bg-gray-200 rounded animate-pulse" /></td>
                <td className="px-4 py-3"><div className="w-32 h-3 bg-gray-200 rounded animate-pulse" /></td>
                <td className="px-4 py-3" />
              </tr>
            ))}
            {!loading && complaints.map((c) => {
              const isSelected = selected?.id === c.id;
              const isPending = c.category === "Analysing…";
              const mergedChildren = mergedChildrenMap.get(c.id) ?? [];
              const hasChildren = mergedChildren.length > 0;
              const isExpanded = expandedRows.has(c.id);

              return (
                <Fragment key={c.id}>
                  <tr
                    onClick={() => onSelect(c)}
                    className={`border-b border-gray-50 cursor-pointer transition-colors last:border-0 ${
                      isSelected ? "bg-ub-blue-light" : "hover:bg-slate-50"
                    }`}
                  >
                    {/* Chevron column — fixed w-8 */}
                    <td className="w-8 px-2 py-3">
                      {hasChildren ? (
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleExpand(c.id); }}
                          className="flex items-center justify-center w-6 h-6 rounded hover:bg-slate-200 text-gray-400"
                        >
                          {isExpanded
                            ? <ChevronDown size={14} />
                            : <ChevronRight size={14} />
                          }
                        </button>
                      ) : (
                        <div className="w-8" />
                      )}
                    </td>

                    {/* ID + Merged badge */}
                    <td className="px-4 py-3 text-xs font-mono font-semibold text-ub-blue whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        {c.id}
                        {hasChildren && (
                          <span className="px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-100 text-indigo-700">
                            Merged ({mergedChildren.length})
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Customer */}
                    <td className="px-4 py-3">
                      <div className="font-semibold text-gray-800 whitespace-nowrap text-sm">
                        {c.customer}
                      </div>
                    </td>

                    {/* Channel */}
                    <td className="px-4 py-3">
                      <ChannelBadge channel={c.channel} />
                    </td>

                    {/* Category / Type */}
                    <td className="px-4 py-3">
                      <div
                        className={`whitespace-nowrap ${isPending ? "text-xs text-slate-400 italic" : "text-sm text-gray-800"}`}
                      >
                        {c.category}
                      </div>
                      {!isPending && c.type && (
                        <div className="text-xs text-gray-400">{c.type}</div>
                      )}
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3">
                      <StatusBadge status={c.status} />
                    </td>

                    {/* SLA */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <SlaBadge breached={c.slaBreached} label={c.slaRemaining} />
                    </td>

                    {/* Customer History summary */}
                    <td className="px-3 py-2 max-w-[192px]">
                      <CustomerSummaryCard cifId={cifIdMap?.get(c.id)} compact />
                    </td>

                    {/* Duplicate flag */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      {c.duplicateStatus && c.duplicateStatus !== 'merged' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                          Duplicate
                        </span>
                      )}
                    </td>
                  </tr>

                  {/* Expanded merged children panel */}
                  {hasChildren && (
                    <tr key={`${c.id}-children`}>
                      <td colSpan={HEADERS.length} className="p-0">
                        <MergedChildrenPanel
                          mergedItems={mergedChildren}
                          isExpanded={isExpanded}
                          onSelect={onSelect}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>

        {!loading && complaints.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <div className="text-sm">
              No complaints match the current filters.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { BookOpen, Clock } from "lucide-react";
import { api } from "../../lib/api";
import type { CustomerSummary } from "../../types";

interface Props {
  cifId: string | null | undefined;
  compact?: boolean;
}

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diff < 1) return "just now";
  if (diff < 60) return `${diff}m ago`;
  const h = Math.floor(diff / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function CustomerSummaryCard({ cifId, compact = false }: Props) {
  const [summary, setSummary] = useState<CustomerSummary | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!cifId) return;
    setLoading(true);
    api.customers
      .getSummary(cifId)
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setLoading(false));
  }, [cifId]);

  if (!cifId) return null;

  if (loading) {
    return <div className="animate-pulse rounded-lg bg-slate-100 h-12 w-full" />;
  }

  if (!summary?.summary_text) {
    return (
      <p className="text-xs text-slate-400 italic">No complaint history on record.</p>
    );
  }

  if (compact) {
    return (
      <p className="text-xs text-slate-600 line-clamp-1 leading-relaxed">
        {summary.summary_text}
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50/60 p-3 space-y-1.5">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-ub-blue">
        <BookOpen size={12} />
        Customer History Summary
      </div>
      <p className="text-xs text-slate-700 leading-relaxed">{summary.summary_text}</p>
      <div className="flex items-center gap-1 text-[10px] text-slate-400">
        <Clock size={10} />
        Based on {summary.complaint_count} complaint
        {summary.complaint_count !== 1 ? "s" : ""} · Updated{" "}
        {timeAgo(summary.last_updated)}
      </div>
    </div>
  );
}

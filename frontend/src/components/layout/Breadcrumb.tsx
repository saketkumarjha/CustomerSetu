import { ChevronRight } from "lucide-react";
import type { TabId } from "../../types";

interface Props {
  active: TabId;
}

const LABELS: Record<TabId, { label: string; desc: string }> = {
  overview: { label: "Overview", desc: "Summary and recent complaints" },
  complaints: { label: "All Complaints", desc: "Search and review complaints" },
  submit: {
    label: "Register Complaint",
    desc: "Enter a complaint for analysis",
  },
  pipeline: { label: "AI Pipeline", desc: "Step-by-step analysis view" },
  analytics: { label: "Analytics", desc: "Volumes, satisfaction, and trends" },
  "analytics-overview": {
    label: "Analytics Overview",
    desc: "7-day complaint analytics and insights",
  },
  "analytics-ai-performance": {
    label: "AI Performance",
    desc: "Pipeline agent metrics and performance",
  },
  "analytics-customer-feedback": {
    label: "Customer Feedback",
    desc: "Customer satisfaction trends and insights",
  },
  "analytics-root-cause": {
    label: "Root-Cause Analysis",
    desc: "AI-powered analysis of low-rated complaints",
  },
  rbi: { label: "RBI Compliance", desc: "Regulatory reporting and deadlines" },
  sla: { label: "SLA Tracker", desc: "Targets and overdue cases" },
  kb: {
    label: "KB Admin",
    desc: "Manage knowledge base entries and review queue",
  },
};

export function Breadcrumb({ active }: Props) {
  const { label, desc } = LABELS[active];
  return (
    <div className="mb-3 md:mb-4 flex-shrink-0">
      <nav className="flex items-center gap-1 md:gap-1.5 text-xs text-gray-400">
        <span className="hidden sm:inline">Dashboard</span>
        <ChevronRight size={12} className="hidden sm:inline" />
        <span className="text-ub-blue font-semibold">{label}</span>
      </nav>
      <p className="text-xs text-gray-400 mt-0.5 hidden sm:block">{desc}</p>
    </div>
  );
}

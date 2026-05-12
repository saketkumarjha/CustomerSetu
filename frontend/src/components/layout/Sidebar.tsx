import { useState } from "react";
import {
  BarChart2,
  ClipboardList,
  Cpu,
  TrendingUp,
  X,
  Shield,
  Clock,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Activity,
  Users,
  AlertTriangle,
  UserCircle2,
} from "lucide-react";
import type { TabId } from "../../types";

interface Props {
  active: TabId;
  setActive: (id: TabId) => void;
  isOpen: boolean;
  onClose: () => void;
}

type NavItem = {
  id: TabId;
  icon: React.ReactNode;
  label: string;
  badge?: string;
  children?: { id: TabId; icon: React.ReactNode; label: string }[];
};

const TABS: NavItem[] = [
  { id: "overview", icon: <BarChart2 size={16} />, label: "Overview" },
  {
    id: "complaints",
    icon: <ClipboardList size={16} />,
    label: "All Complaints",
  },
  { id: "pipeline", icon: <Cpu size={16} />, label: "AI Pipeline" },
  { id: "agent", icon: <UserCircle2 size={16} />, label: "Agent Desk" },
  {
    id: "analytics",
    icon: <TrendingUp size={16} />,
    label: "Analytics",
    children: [
      {
        id: "analytics-overview",
        icon: <BarChart2 size={13} />,
        label: "Analytics Overview",
      },
      {
        id: "analytics-ai-performance",
        icon: <Activity size={13} />,
        label: "AI Performance",
      },
      {
        id: "analytics-customer-feedback",
        icon: <Users size={13} />,
        label: "Customer Feedback",
      },
      {
        id: "analytics-root-cause",
        icon: <AlertTriangle size={13} />,
        label: "Root-Cause Analysis",
      },
    ],
  },
  { id: "rbi", icon: <Shield size={16} />, label: "RBI Compliance" },
  { id: "sla", icon: <Clock size={16} />, label: "SLA Tracker" },
  { id: "kb", icon: <BookOpen size={16} />, label: "KB Admin", badge: "ADMIN" },
];

const ANALYTICS_IDS: TabId[] = [
  "analytics",
  "analytics-overview",
  "analytics-ai-performance",
  "analytics-customer-feedback",
  "analytics-root-cause",
];

export function Sidebar({ active, setActive, isOpen, onClose }: Props) {
  const [analyticsOpen, setAnalyticsOpen] = useState<boolean>(
    ANALYTICS_IDS.includes(active),
  );

  function handleTabClick(id: TabId) {
    setActive(id);
    onClose();
  }

  function handleAnalyticsToggle() {
    setAnalyticsOpen((o) => !o);
  }

  const sidebarContent = (
    <aside className="flex flex-col h-full py-4 bg-white/75 backdrop-blur-md border-r border-slate-200/90 w-56 lg:w-48">
      {/* Mobile close */}
      <div className="flex items-center justify-between px-4 mb-2 lg:hidden">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
          Navigation
        </span>
        <button
          type="button"
          onClick={onClose}
          className="w-8 h-8 rounded-md flex items-center justify-center text-slate-400 hover:bg-slate-100 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <div className="px-4 pb-1">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide hidden lg:block">
          Menu
        </span>
      </div>

      <nav className="flex flex-col gap-0.5 flex-1 px-1 overflow-y-auto">
        {TABS.map((tab) => {
          const hasChildren = !!tab.children?.length;
          const isAnalyticsActive =
            hasChildren && ANALYTICS_IDS.includes(active);

          if (hasChildren) {
            return (
              <div key={tab.id}>
                {/* Parent row — toggles dropdown */}
                <button
                  type="button"
                  onClick={handleAnalyticsToggle}
                  className={`flex items-center gap-3 mx-1 px-3 py-2 rounded-md text-sm font-medium text-left transition-colors border w-full ${
                    isAnalyticsActive
                      ? "bg-ub-blue-light/90 text-ub-blue border-slate-200/80 shadow-sm"
                      : "text-slate-600 border-transparent hover:bg-slate-100/80 hover:text-slate-800"
                  }`}
                >
                  <span
                    className={`flex-shrink-0 ${isAnalyticsActive ? "text-ub-blue" : "text-slate-400"}`}
                  >
                    {tab.icon}
                  </span>
                  <span className="flex-1 truncate">{tab.label}</span>
                  <span className="flex-shrink-0 text-slate-400">
                    {analyticsOpen ? (
                      <ChevronDown size={13} />
                    ) : (
                      <ChevronRight size={13} />
                    )}
                  </span>
                </button>

                {/* Children */}
                {analyticsOpen && (
                  <div className="ml-3 mt-0.5 mb-1 border-l border-slate-200 pl-2 space-y-0.5">
                    {tab.children!.map((child) => {
                      const childActive = active === child.id;
                      return (
                        <button
                          key={child.id}
                          type="button"
                          onClick={() => handleTabClick(child.id)}
                          className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-xs font-medium text-left transition-colors w-full ${
                            childActive
                              ? "bg-ub-blue-light/90 text-ub-blue"
                              : "text-slate-500 hover:bg-slate-100/80 hover:text-slate-800"
                          }`}
                        >
                          <span
                            className={`flex-shrink-0 ${childActive ? "text-ub-blue" : "text-slate-400"}`}
                          >
                            {child.icon}
                          </span>
                          <span className="truncate">{child.label}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }

          const isActive = active === tab.id;
          return (
            <button
              type="button"
              key={tab.id}
              onClick={() => handleTabClick(tab.id)}
              className={`flex items-center gap-3 mx-1 px-3 py-2 rounded-md text-sm font-medium text-left transition-colors border ${
                isActive
                  ? "bg-ub-blue-light/90 text-ub-blue border-slate-200/80 shadow-sm"
                  : "text-slate-600 border-transparent hover:bg-slate-100/80 hover:text-slate-800"
              }`}
            >
              <span
                className={`flex-shrink-0 ${isActive ? "text-ub-blue" : "text-slate-400"}`}
              >
                {tab.icon}
              </span>
              <span className="flex-1 truncate">{tab.label}</span>
              {tab.badge && (
                <span className="text-[10px] bg-ub-red text-white px-1.5 py-0.5 rounded-md font-semibold flex-shrink-0">
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="px-4 py-4 border-t border-slate-200/80 space-y-1.5 mt-auto">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
          System
        </div>
        {[
          { label: "AI agents", value: "10" },
          { label: "Avg. pipeline", value: "~5s" },
          { label: "Uptime", value: "99.98%" },
        ].map((s) => (
          <div key={s.label} className="flex justify-between text-xs">
            <span className="text-slate-400">{s.label}</span>
            <span className="font-semibold text-slate-700">{s.value}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5 mt-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500/90" />
          <span className="text-xs text-slate-600 font-medium">Connected</span>
        </div>
      </div>
    </aside>
  );

  return (
    <>
      <div className="hidden lg:flex flex-shrink-0">{sidebarContent}</div>

      {isOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div
            className="absolute inset-0 bg-slate-900/30 backdrop-blur-[2px]"
            onClick={onClose}
            aria-hidden
          />
          <div className="relative z-50 flex-shrink-0 shadow-xl animate-slide-in-left">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}

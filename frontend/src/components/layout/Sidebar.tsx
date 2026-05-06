import { BarChart2, ClipboardList, Cpu, TrendingUp, X, PlusCircle, Shield, Clock } from 'lucide-react'
import type { TabId } from '../../types'

interface Props {
  active: TabId
  setActive: (id: TabId) => void
  isOpen: boolean
  onClose: () => void
}

const TABS: { id: TabId; icon: React.ReactNode; label: string; badge?: string }[] = [
  { id: 'overview', icon: <BarChart2 size={16} />, label: 'Overview' },
  { id: 'complaints', icon: <ClipboardList size={16} />, label: 'All Complaints' },
  { id: 'submit', icon: <PlusCircle size={16} />, label: 'New Complaint', badge: 'NEW' },
  { id: 'pipeline', icon: <Cpu size={16} />, label: 'AI Pipeline' },
  { id: 'analytics', icon: <TrendingUp size={16} />, label: 'Analytics' },
  { id: 'rbi', icon: <Shield size={16} />, label: 'RBI Compliance' },
  { id: 'sla', icon: <Clock size={16} />, label: 'SLA Tracker' },
]

export function Sidebar({ active, setActive, isOpen, onClose }: Props) {
  function handleTabClick(id: TabId) {
    setActive(id)
    onClose()
  }

  const sidebarContent = (
    <aside className="flex flex-col h-full py-4 bg-white/75 backdrop-blur-md border-r border-slate-200/90 w-56 lg:w-48">
      {/* Mobile close */}
      <div className="flex items-center justify-between px-4 mb-2 lg:hidden">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Navigation</span>
        <button
          type="button"
          onClick={onClose}
          className="w-8 h-8 rounded-md flex items-center justify-center text-slate-400 hover:bg-slate-100 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <div className="px-4 pb-1">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide hidden lg:block">Menu</span>
      </div>

      <nav className="flex flex-col gap-0.5 flex-1 px-1">
        {TABS.map((tab) => {
          const isActive = active === tab.id
          return (
            <button
              type="button"
              key={tab.id}
              onClick={() => handleTabClick(tab.id)}
              className={`flex items-center gap-3 mx-1 px-3 py-2 rounded-md text-sm font-medium text-left transition-colors border ${
                isActive
                  ? 'bg-ub-blue-light/90 text-ub-blue border-slate-200/80 shadow-sm'
                  : 'text-slate-600 border-transparent hover:bg-slate-100/80 hover:text-slate-800'
              }`}
            >
              <span className={`flex-shrink-0 ${isActive ? 'text-ub-blue' : 'text-slate-400'}`}>
                {tab.icon}
              </span>
              <span className="flex-1 truncate">{tab.label}</span>
              {tab.badge && (
                <span className="text-[10px] bg-ub-red text-white px-1.5 py-0.5 rounded-md font-semibold flex-shrink-0">
                  {tab.badge}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      <div className="px-4 py-4 border-t border-slate-200/80 space-y-1.5 mt-auto">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">System</div>
        {[
          { label: 'AI agents', value: '10' },
          { label: 'Avg. pipeline', value: '~5s' },
          { label: 'Uptime', value: '99.98%' },
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
  )

  return (
    <>
      <div className="hidden lg:flex flex-shrink-0">{sidebarContent}</div>

      {isOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
          <div className="relative z-50 flex-shrink-0 shadow-xl animate-slide-in-left">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  )
}

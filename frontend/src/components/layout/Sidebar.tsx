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
    <aside className="flex flex-col h-full py-4 bg-slate-50 border-r border-gray-200 w-56 lg:w-48">
      {/* Mobile close */}
      <div className="flex items-center justify-between px-4 mb-2 lg:hidden">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Navigation</span>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* Menu section label */}
      <div className="px-4 pb-1">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide hidden lg:block">Menu</span>
      </div>

      <nav className="flex flex-col gap-0.5 flex-1">
        {TABS.map((tab) => {
          const isActive = active === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => handleTabClick(tab.id)}
              className={`flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-left transition-all border-r-2 group ${
                isActive
                  ? 'bg-blue-50 text-ub-blue border-ub-blue'
                  : 'text-gray-500 border-transparent hover:bg-gray-100 hover:text-gray-700'
              }`}
            >
              <span className={`flex-shrink-0 ${isActive ? 'text-ub-blue' : 'text-gray-400 group-hover:text-gray-600'}`}>
                {tab.icon}
              </span>
              <span className="flex-1 truncate">{tab.label}</span>
              {tab.badge && (
                <span className="text-xs bg-ub-red text-white px-1.5 py-0.5 rounded-full font-bold flex-shrink-0">
                  {tab.badge}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Bottom system info */}
      <div className="px-4 py-4 border-t border-gray-200 space-y-1.5">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">System Status</div>
        {[
          { label: 'AI Agents', value: '10', color: 'text-green-600' },
          { label: 'Avg pipeline', value: '~5 sec', color: 'text-ub-blue' },
          { label: 'Uptime', value: '99.98%', color: 'text-green-600' },
        ].map((s) => (
          <div key={s.label} className="flex justify-between text-xs">
            <span className="text-gray-400">{s.label}</span>
            <span className={`font-semibold ${s.color}`}>{s.value}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5 mt-2">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-green-600 font-medium">Backend connected</span>
        </div>
      </div>
    </aside>
  )

  return (
    <>
      {/* Desktop — always visible */}
      <div className="hidden lg:flex flex-shrink-0">{sidebarContent}</div>

      {/* Mobile — overlay drawer */}
      {isOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black bg-opacity-40" onClick={onClose} />
          <div className="relative z-50 flex-shrink-0 shadow-xl animate-slide-in-left">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  )
}

import { ChevronRight } from 'lucide-react'
import type { TabId } from '../../types'

interface Props {
  active: TabId
}

const LABELS: Record<TabId, { label: string; desc: string }> = {
  overview: { label: 'Overview', desc: 'Dashboard summary and recent activity' },
  complaints: { label: 'All Complaints', desc: 'View, search and manage all complaints' },
  submit: { label: 'Register Complaint', desc: 'Submit a new customer complaint for AI analysis' },
  pipeline: { label: 'AI Pipeline', desc: 'Live AI analysis with 10 specialised agents' },
  analytics: { label: 'Analytics', desc: 'Performance metrics and trend reports' },
  rbi: { label: 'RBI Compliance', desc: 'Regulatory compliance tracking and TAT monitoring' },
  sla: { label: 'SLA Tracker', desc: 'Service level agreement monitoring and breach prediction' },
}

export function Breadcrumb({ active }: Props) {
  const { label, desc } = LABELS[active]
  return (
    <div className="mb-3 md:mb-4 flex-shrink-0">
      <nav className="flex items-center gap-1 md:gap-1.5 text-xs text-gray-400">
        <span className="hidden sm:inline">Dashboard</span>
        <ChevronRight size={12} className="hidden sm:inline" />
        <span className="text-ub-blue font-semibold">{label}</span>
      </nav>
      <p className="text-xs text-gray-400 mt-0.5 hidden sm:block">{desc}</p>
    </div>
  )
}

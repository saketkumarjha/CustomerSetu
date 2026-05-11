import { ChevronRight } from 'lucide-react'
import type { TabId } from '../../types'

interface Props {
  active: TabId
}

const LABELS: Record<TabId, { label: string; desc: string }> = {
  overview: { label: 'Overview', desc: 'Summary and recent complaints' },
  complaints: { label: 'All Complaints', desc: 'Search and review complaints' },
  agentDesk: { label: 'Agent desk', desc: 'Your queue, your numbers, and the next case to open' },
  submit: { label: 'Register Complaint', desc: 'Enter a complaint for analysis' },
  pipeline: { label: 'AI Pipeline', desc: 'Step-by-step analysis view' },
  analytics: { label: 'Analytics', desc: 'Volumes, satisfaction, and trends' },
  feedback: { label: 'Feedback & dataset', desc: 'CSAT, surveys, and fine-tuning export' },
  rbi: { label: 'RBI Compliance', desc: 'Regulatory reporting and deadlines' },
  sla: { label: 'SLA Tracker', desc: 'Targets and overdue cases' },
  kb: { label: 'KB Admin', desc: 'Manage knowledge base entries and review queue' },
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

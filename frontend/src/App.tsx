import { useState } from 'react'
import type { TabId } from './types'
import { Header } from './components/layout/Header'
import { Sidebar } from './components/layout/Sidebar'
import { Breadcrumb } from './components/layout/Breadcrumb'
import { OverviewTab } from './components/overview/OverviewTab'
import { ComplaintsTab } from './components/complaints/ComplaintsTab'
import { SubmitTab } from './components/submit/SubmitTab'
import { PipelineTab } from './components/pipeline/PipelineTab'
import { AnalyticsTab } from './components/analytics/AnalyticsTab'
import { RBITab } from './components/rbi/RBITab'
import { SLATab } from './components/sla/SLATab'

export default function App() {
  const [active, setActive] = useState<TabId>('overview')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-slate-100 via-slate-50 to-ub-blue-light/50 font-sans">
      <Header
        sidebarOpen={sidebarOpen}
        onMenuToggle={() => setSidebarOpen((o) => !o)}
      />

      <div className="flex flex-1 overflow-hidden" style={{ height: 'calc(100vh - 56px)' }}>
        <Sidebar
          active={active}
          setActive={setActive}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        <main className="flex-1 overflow-auto p-4 md:p-6 min-w-0">
          <Breadcrumb active={active} />

          {active === 'overview' && <OverviewTab setActive={setActive} />}
          {active === 'complaints' && <ComplaintsTab setActive={setActive} />}
          {active === 'submit' && <SubmitTab setActive={setActive} />}
          {active === 'pipeline' && <PipelineTab />}
          {active === 'analytics' && <AnalyticsTab />}
          {active === 'rbi' && <RBITab />}
          {active === 'sla' && <SLATab />}
        </main>
      </div>
    </div>
  )
}

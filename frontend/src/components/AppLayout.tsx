import { useState } from 'react'
import { Outlet, useParams } from 'react-router-dom'
import { useHealth } from '../api/hooks'
import AgentPanel from './AgentPanel'
import JournalPanel from './JournalPanel'
import Nav from './Nav'
import './AppLayout.css'

type PanelTab = 'agent' | 'journal' | null

const TABS: { id: Exclude<PanelTab, null>; label: string }[] = [
  { id: 'agent', label: '✨ Agent' },
  { id: 'journal', label: '📝 Journal' },
]

/** Wraps one project's detail page — the Agent/Journal file-drawer side panel, ported exactly
 * from Value Stream's MapLayout.tsx/.css (same bottom-right tab rail: rests flush closed or
 * against the open panel's edge, the active tab pulls out further overlapping the main
 * content, click-to-close instead of a separate collapse button). See that component for the
 * full reasoning — this is a straight port, not a redesign. Only scoped to the detail page
 * (not the project list) since both tabs need a specific project to be about. */
export default function AppLayout() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: health } = useHealth()
  const [activeTab, setActiveTab] = useState<PanelTab>(null)

  const selectTab = (tab: PanelTab) => {
    setActiveTab(tab)
    setTimeout(() => window.dispatchEvent(new Event('resize')), 80)
  }

  if (!projectId) return null

  return (
    <div className="app-layout">
      <Nav />
      <div className={`app-layout__row${activeTab ? ' app-layout__row--panel-open' : ''}`}>
        <div className="app-layout__main">
          <Outlet />
        </div>

        {activeTab && (
          <aside className="side-panel">
            <div className="side-panel__body">
              {activeTab === 'agent' ? (
                <AgentPanel
                  depotProjectId={projectId}
                  aiConfigured={health?.ai_configured ?? false}
                />
              ) : (
                <JournalPanel depotProjectId={projectId} />
              )}
            </div>
          </aside>
        )}

        <div className="app-layout__tab-rail">
          {TABS.map((t) => {
            const isActive = activeTab === t.id
            const bareLabel = t.label.replace(/^\S+\s/, '')
            return (
              <button
                key={t.id}
                className={`app-layout__tab-rail-btn${isActive ? ' app-layout__tab-rail-btn--active' : ''}`}
                onClick={() => selectTab(isActive ? null : t.id)}
                title={isActive ? `Collapse ${bareLabel}` : `Open ${bareLabel}`}
              >
                {t.label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

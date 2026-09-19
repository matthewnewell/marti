import { DrawerLayout } from '@conways/drawer'
import { Outlet, useParams } from 'react-router-dom'
import { useHealth } from '../api/hooks'
import Nav from './Nav'
import './AppLayout.css'

/** One project's detail page inside the ecosystem's shared Agent | Journal drawer
 * (@conways/drawer). Only the project-scoped chat endpoint and starters are MARTI's own. */
export default function AppLayout() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: health } = useHealth()

  if (!projectId) return null

  return (
    <div className="app-layout">
      <Nav />
      <DrawerLayout
        agent={{
          chatUrl: `/api/projects/${projectId}/chat`,
          aiConfigured: health?.ai_configured ?? false,
          intro: "Ask about this project's materials, acquisition status, routings, or why it's flagged.",
          starters: [
            'What needs my attention on this project?',
            'Why is this flagged as at-risk?',
            "What's the status of open acquisition orders?",
          ],
        }}
        journal={{ projectId }}
      >
        <Outlet />
      </DrawerLayout>
    </div>
  )
}

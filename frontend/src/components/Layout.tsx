import { DrawerLayout } from '@conways/drawer'
import { Outlet } from 'react-router-dom'
import { useHealth } from '../api/hooks'
import { usePersona } from '../lib/persona'
import { useScope } from '../lib/scope'
import Nav from './Nav'
import './Layout.css'

/** Every page sits under the nav. With a project picked, the page also gets the ecosystem's
 * shared Agent | Journal drawer (@conways/drawer) for that project. */
export default function Layout() {
  const { projectId } = useScope()
  const { data: health } = useHealth()
  const { persona } = usePersona()

  return (
    <div className="app-layout">
      <Nav />
      {projectId ? (
        <DrawerLayout
          key={projectId}
          storageKey="marti.drawer"
          agent={{
            chatUrl: `/api/projects/${projectId}/chat`,
            aiConfigured: health?.ai_configured ?? false,
            intro:
              "Ask about this project's material acquisition, where it is in the routing, or why it will or won't make its need-by date.",
            starters: [
              'Will this project make its need-by date? Why or why not?',
              "What's this project waiting on right now?",
              'What would it take to pull the finish date in?',
            ],
          }}
          journal={{ projectId, personId: persona?.id }}
        >
          <Outlet />
        </DrawerLayout>
      ) : (
        <main className="app-main">
          <Outlet />
        </main>
      )}
    </div>
  )
}

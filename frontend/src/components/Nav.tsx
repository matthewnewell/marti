import { AppHeader, tabClass } from '@conways/drawer'
import { Link, NavLink } from 'react-router-dom'
import { useHotFlags, useProjects } from '../api/hooks'
import { useScope } from '../lib/scope'
import './Nav.css'

/** Left to right the tabs spell the app: Material & Acquisition, Routing, Triage & Impact, then
 * Constraints. The project picker on the right scopes the first two (and opens the Agent |
 * Journal drawer); the bell is the hot flags Triage raises. */
const LINKS = [
  { to: '/material', label: 'Material & Acquisition' },
  { to: '/routing', label: 'Routing' },
  { to: '/triage', label: 'Triage & Impact' },
  { to: '/constraints', label: 'Constraints' },
]

export default function Nav() {
  const { data: flags } = useHotFlags('active')
  const { data: projects } = useProjects()
  const { projectId, setProjectId } = useScope()
  const open = flags?.hot_flags.filter((f) => f.status === 'open').length ?? 0

  return (
    <AppHeader
      brand={
        <NavLink to="/about" className="ch-brand">
          MARTI
        </NavLink>
      }
      right={
        <>
          <label className={`mt-nav__scope${projectId ? ' mt-nav__scope--on' : ''}`}>
            <span className="mt-nav__scope-label">Project</span>
            <select value={projectId ?? ''} onChange={(e) => setProjectId(e.target.value || null)}>
              <option value="">All projects</option>
              {projects?.projects.map((p) => (
                <option key={p.depot_project_id} value={p.depot_project_id}>
                  #{p.rank} {p.name ?? 'Unknown project'}
                </option>
              ))}
            </select>
          </label>
          <Link to="/hot-flags" className="mt-nav__bell" title={`${open} open hot flag${open === 1 ? '' : 's'}`}>
            🔔{open > 0 && <span className="mt-nav__badge">{open}</span>}
          </Link>
        </>
      }
    >
      {LINKS.map((l) => (
        <NavLink key={l.to} to={l.to} className={({ isActive }) => tabClass(isActive)}>
          {l.label}
        </NavLink>
      ))}
    </AppHeader>
  )
}

import { AppHeader, tabClass } from '@conways/drawer'
import { Link, NavLink } from 'react-router-dom'
import { useHotFlags } from '../api/hooks'
import './Nav.css'

/** Left to right the tabs spell the app: Material & Acquisition, Routing, Triage & Impact, then
 * Constraints. The bell is the hot flags Triage raises. The project picker isn't here: it sits in
 * the headers of the two pages it scopes (components/ProjectPicker). */
const LINKS = [
  { to: '/material', label: 'Material & Acquisition' },
  { to: '/routing', label: 'Routing' },
  { to: '/triage', label: 'Triage & Impact' },
  { to: '/constraints', label: 'Constraints' },
]

export default function Nav() {
  const { data: flags } = useHotFlags('active')
  const open = flags?.hot_flags.filter((f) => f.status === 'open').length ?? 0

  return (
    <AppHeader
      brand={
        <NavLink to="/about" className="ch-brand">
          MARTI
        </NavLink>
      }
      right={
        <Link to="/hot-flags" className="mt-nav__bell" title={`${open} open hot flag${open === 1 ? '' : 's'}`}>
          🔔{open > 0 && <span className="mt-nav__badge">{open}</span>}
        </Link>
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

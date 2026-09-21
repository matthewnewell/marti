import { NavLink } from 'react-router-dom'
import './Nav.css'

/** Persistent top navbar — same pattern as the sibling apps: brand links to the splash page,
 * one top-level link for the rest. */
export default function Nav() {
  return (
    <nav className="mt-nav">
      <NavLink to="/about" className="mt-nav__brand">
        MARTI
      </NavLink>
      <div className="mt-nav__links">
        <NavLink
          to="/"
          end
          className={({ isActive }) => `mt-nav__link ${isActive ? 'mt-nav__link--active' : ''}`}
        >
          Projects
        </NavLink>
      </div>
    </nav>
  )
}

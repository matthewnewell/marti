import { NavLink } from 'react-router-dom'
import './Nav.css'

export default function Nav() {
  return (
    <nav className="mt-nav">
      <NavLink to="/" className="mt-nav__brand">
        MARTI
      </NavLink>
      <div className="mt-nav__right">
        <NavLink to="/about" className="mt-nav__link">
          About
        </NavLink>
      </div>
    </nav>
  )
}

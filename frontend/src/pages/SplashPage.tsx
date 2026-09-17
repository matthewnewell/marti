import Nav from '../components/Nav'
import './SplashPage.css'

export default function SplashPage() {
  return (
    <div className="splash-page">
      <Nav />
      <div className="splash-page__content">
        <h1>MARTI</h1>
        <p className="splash-page__sub">Material · Acquisition · Routings · Tension · Impact</p>
        <p>
          One place for the manufacturing side of a project: what's on order, what's being
          built, and whether where it sits in priority actually matches when it's due.
        </p>
        <ul className="splash-page__list">
          <li>
            <strong>Material &amp; Acquisition</strong> — mocked S4 material masters and
            purchase orders (no live S4 integration yet).
          </li>
          <li>
            <strong>Routings</strong> — mocked manufacturing operations and their status.
          </li>
          <li>
            <strong>Tension</strong> — a priority per project, set by whoever owns it.
          </li>
          <li>
            <strong>Impact</strong> — computed: a low-priority project with an approaching due
            date is flagged automatically.
          </li>
        </ul>
        <p className="splash-page__note">
          A project shows up here if Conway's Depot says it has a manufacturing component, or
          if it has an in-house-produced material on file — whichever comes first.
        </p>
      </div>
    </div>
  )
}

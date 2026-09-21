import { Link } from 'react-router-dom'
import Nav from '../components/Nav'
import './SplashPage.css'

const STAGES = [
  { letter: 'M', label: 'Material', note: 'S4 master (mock)' },
  { letter: 'A', label: 'Acquisition', note: 'Orders & promise dates' },
  { letter: 'R', label: 'Routing', note: 'Operations & status' },
  { letter: 'T', label: 'Tradeoffs', note: 'Priority per project' },
  { letter: 'I', label: 'Impact', note: 'Computed, never stored' },
]

const FEATURES = [
  {
    title: 'Material, orders, and routings',
    body: 'What is on order, what is being built, and where each operation stands — one view per project. Mocked S4 data for now; no live S4 integration yet.',
  },
  {
    title: 'Tradeoffs you can see',
    body: 'Every manufacturing project carries a priority and a due date, set by whoever owns it. Competing demands on the shop floor stop being a hallway negotiation.',
  },
  {
    title: 'Impact, computed for you',
    body: 'A low-priority project with an approaching due date is flagged automatically. A project appears here when Conway’s Depot marks it as manufacturing, or when it has an in-house-produced material on file.',
  },
]

export default function SplashPage() {
  return (
    <div className="splash-page">
      <Nav />
      <div className="splash-page__scroll">
        <div className="splash-page__content">
          <header className="splash-hero">
            <h1 className="splash-hero__title">Material Acquisition, Routing, Tradeoffs and Impact</h1>
            <p className="splash-hero__sub">
              See what a manufacturing project needs, what it is competing with, and what slips when
              priority and due date disagree.
            </p>
            <div className="splash-hero__actions">
              <Link className="splash-btn splash-btn--primary" to="/">
                View projects
              </Link>
            </div>
          </header>

          <figure className="splash-figure">
            <ol className="splash-flow">
              {STAGES.map((s, i) => (
                <li key={s.letter} className="splash-flow__step">
                  <div className={`splash-flow__badge${s.letter === 'I' ? ' splash-flow__badge--impact' : ''}`}>
                    {s.letter}
                  </div>
                  <div className="splash-flow__label">{s.label}</div>
                  <div className="splash-flow__note">{s.note}</div>
                  {i < STAGES.length - 1 && <span className="splash-flow__arrow" aria-hidden="true">▶</span>}
                </li>
              ))}
            </ol>
          </figure>

          <div className="splash-grid">
            {FEATURES.map((f) => (
              <div key={f.title} className="splash-card">
                <div className="splash-card__heading">{f.title}</div>
                <p className="splash-card__body">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

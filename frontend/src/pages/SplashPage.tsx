import { Link } from 'react-router-dom'
import './SplashPage.css'

// Each stage opens the page that covers it: M and A share Material & Acquisition, T and I share
// Triage & Impact.
const STAGES = [
  { letter: 'M', label: 'Material', note: 'S4 master: exists or not', to: '/material' },
  { letter: 'A', label: 'Acquisition', note: 'PR → PO → receipt', to: '/material' },
  { letter: 'R', label: 'Routing', note: 'Where it is, how long', to: '/routing' },
  { letter: 'T', label: 'Triage', note: 'Leadership’s stack rank', to: '/triage' },
  { letter: 'I', label: 'Impact', note: 'Who misses need-by', to: '/triage' },
]

const FEATURES = [
  {
    title: 'Material acquisition',
    body: 'Every component a build needs, from the S4 material master (or the lack of one) through PR, PO, supplier confirmation, receipt and inspection. Each is dated against when the step that uses it is scheduled to start.',
  },
  {
    title: 'Routing, dwell and constraints',
    body: 'Where every build is, from the top assembly down through its sub-assemblies: the step each order is at, how long it has sat there, open rework and MRB holds, and which steps can’t start for lack of material. The Constraints view shows where queues are building across all projects.',
  },
  {
    title: 'Triage and its Impact',
    body: 'Leadership ranks the projects. Rank decides who gets shared work centers first. Try a new order, or one MARTI suggests, and see which need-by dates move before committing it. A commit raises hot flags on whatever is blocking the projects that moved up. Forecasts use S4 standard hours only.',
  },
]

export default function SplashPage() {
  return (
    <div className="splash-page">
      <div className="splash-page__scroll">
        <div className="splash-page__content">
          <header className="splash-hero">
            <h1 className="splash-hero__title">
              <span className="splash-hero__line">Material Acquisition, Routing,</span>{' '}
              <span className="splash-hero__line">Triage and Impact</span>
            </h1>
            <p className="splash-hero__sub">
              See what each build is waiting on, where the shop is backing up, and whose need-by date
              slips when leadership reorders the work.
            </p>
          </header>

          <figure className="splash-figure">
            <ol className="splash-flow">
              {STAGES.map((s, i) => (
                <li key={s.letter} className="splash-flow__step">
                  <Link className="splash-flow__link" to={s.to}>
                    <div className={`splash-flow__badge${s.letter === 'I' ? ' splash-flow__badge--impact' : ''}`}>
                      {s.letter}
                    </div>
                    <div className="splash-flow__label">{s.label}</div>
                    <div className="splash-flow__note">{s.note}</div>
                  </Link>
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

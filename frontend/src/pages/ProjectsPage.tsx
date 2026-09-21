import { Link } from 'react-router-dom'
import { useProjects } from '../api/hooks'
import { PRIORITY_LABEL } from '../api/types'
import Nav from '../components/Nav'
import './ProjectsPage.css'

export default function ProjectsPage() {
  const { data, isLoading } = useProjects()

  return (
    <div className="projects-page">
      <Nav />
      <div className="projects-page__content">
        <h1>Manufacturing projects</h1>
        <p className="projects-page__sub">
          Projects Conway's Depot flags as having a manufacturing component, or that have an
          in-house-produced material on file.
        </p>

        {isLoading ? (
          <p className="projects-page__empty">Loading…</p>
        ) : data?.depot_reachable === false ? (
          <p className="projects-page__empty">
            Conway's Depot is unreachable — MARTI needs it to know which projects exist.
          </p>
        ) : !data || data.projects.length === 0 ? (
          <p className="projects-page__empty">No manufacturing projects found yet.</p>
        ) : (
          <div className="projects-page__list">
            {data.projects.map((p) => (
              <Link key={p.depot_project_id} to={`/projects/${p.depot_project_id}`} className="project-card">
                <div className="project-card__top">
                  <span className="project-card__name">{p.name}</span>
                  {p.tradeoff && (
                    <span className={`project-card__priority project-card__priority--${p.tradeoff.priority}`}>
                      {PRIORITY_LABEL[p.tradeoff.priority]}
                    </span>
                  )}
                </div>
                {p.tradeoff?.impact.flagged && (
                  <div className="project-card__impact">⚠ {p.tradeoff.impact.reason}</div>
                )}
                <div className="project-card__rollup">
                  <span>
                    Acquisition: {p.acquisition_orders_open} open / {p.acquisition_orders_total}
                  </span>
                  <span>
                    Routing: {p.routing_ops_open} open / {p.routing_ops_total}
                  </span>
                  <span className="project-card__source">
                    via {p.manufacturing_source === 'depot' ? 'Depot flag' : 'material data'}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

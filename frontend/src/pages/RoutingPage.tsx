import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useRouting } from '../api/hooks'
import ProjectStrip from '../components/ProjectStrip'
import RoutingTree from '../components/RoutingTree'
import { useScope } from '../lib/scope'
import './RoutingPage.css'

/** R: where every production order is in its routing, as an assembly tree per project. */
export default function RoutingPage() {
  const { projectId, setProjectId } = useScope()
  const { data, isLoading } = useRouting(projectId)
  const [problemsOnly, setProblemsOnly] = useState(false)
  const [params] = useSearchParams()
  const focus = params.get('focus')

  return (
    <div className="page__content">
      <h1>Routing</h1>
      <p className="page__sub">
        Where every build is: each assembly and the sub-assemblies under it, the step it's at, how long it's sat there,
        and what's held, short on material or carrying an open quality notification. <strong>Critical</strong> marks the
        chain of orders setting the finish date. Click an order to see its operations.
      </p>

      <div className="toolbar">
        <span className="toolbar__count">
          {data?.projects.length ?? 0} project{data?.projects.length === 1 ? '' : 's'}
        </span>
        <label className="toggle">
          <input type="checkbox" checked={problemsOnly} onChange={(e) => setProblemsOnly(e.target.checked)} />
          Problems and critical chain only
        </label>
      </div>

      {isLoading || !data ? (
        <p className="page__empty">Loading…</p>
      ) : (
        data.projects.map((p) =>
          projectId ? (
            <div key={p.depot_project_id}>
              <ProjectStrip row={p} />
              <RoutingTree roots={p.tree} problemsOnly={problemsOnly} focus={focus} projectId={p.depot_project_id} issues={p.issues} />
            </div>
          ) : (
            <section key={p.depot_project_id} className="rp-project">
              <div className="rp-project__head">
                <span className="rp-project__rank">#{p.rank}</span>
                <button className="rp-project__name" onClick={() => setProjectId(p.depot_project_id)}>
                  {p.name ?? 'Unknown project'}
                </button>
                <span className="muted">
                  {p.size.parts_left} part{p.size.parts_left === 1 ? '' : 's'} · {p.size.ops_left} ops ·{' '}
                  {p.size.std_hours_left} std h left
                </span>
              </div>
              <RoutingTree roots={p.tree} problemsOnly={problemsOnly} focus={focus} projectId={p.depot_project_id} issues={p.issues} />
            </section>
          ),
        )
      )}
    </div>
  )
}

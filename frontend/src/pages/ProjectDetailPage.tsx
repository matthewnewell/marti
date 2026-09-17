import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useProject, useUpdateTension } from '../api/hooks'
import { PRIORITIES, PRIORITY_LABEL, type Priority } from '../api/types'
import './ProjectDetailPage.css'

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: project, isLoading } = useProject(projectId)
  const updateTension = useUpdateTension(projectId ?? '')

  const [priority, setPriority] = useState<Priority>('medium')
  const [dueDate, setDueDate] = useState('')

  useEffect(() => {
    if (project?.tension) {
      setPriority(project.tension.priority)
      setDueDate(project.tension.due_date ?? '')
    }
  }, [project?.tension])

  if (isLoading) return <div className="project-detail__loading">Loading…</div>
  if (!project) return <div className="project-detail__loading">Project not found.</div>

  function saveTension() {
    updateTension.mutate({ priority, due_date: dueDate || null })
  }

  return (
    <div className="project-detail">
      <Link to="/" className="project-detail__back">
        ← All manufacturing projects
      </Link>
      <h1>{project.name}</h1>

      <section className="project-detail__section">
        <h2>Tension</h2>
        <div className="project-detail__tension-form">
          <label>
            Priority
            <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {PRIORITY_LABEL[p]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Due date
            <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </label>
          <button className="mt-btn mt-btn--primary" onClick={saveTension} disabled={updateTension.isPending}>
            {updateTension.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
        {project.tension && (
          <div
            className={`project-detail__impact${project.tension.impact.flagged ? ' project-detail__impact--flagged' : ''}`}
          >
            {project.tension.impact.flagged ? '⚠ ' : '✓ '}
            {project.tension.impact.reason}
          </div>
        )}
      </section>

      <section className="project-detail__section">
        <h2>Materials</h2>
        {project.materials.length === 0 ? (
          <p className="project-detail__empty">No materials on file for this project.</p>
        ) : (
          project.materials.map((m) => (
            <div key={m.id} className="material-card">
              <div className="material-card__top">
                <span className="material-card__number">{m.material_number}</span>
                <span className="material-card__proc-type" title="Procurement type">
                  {m.procurement_type}
                </span>
              </div>
              {m.description && <p className="material-card__desc">{m.description}</p>}

              {m.routings.length > 0 && (
                <div className="material-card__group">
                  <h3>Routings</h3>
                  {m.routings.map((r) => (
                    <div key={r.id} className="material-card__row">
                      <span>
                        {r.operation_seq} · {r.operation_name}
                        {r.work_center && ` (${r.work_center})`}
                      </span>
                      <span className={`status-pill status-pill--${r.status}`}>{r.status.replace('_', ' ')}</span>
                    </div>
                  ))}
                </div>
              )}

              {m.acquisition_orders.length > 0 && (
                <div className="material-card__group">
                  <h3>Acquisition</h3>
                  {m.acquisition_orders.map((a) => (
                    <div key={a.id} className="material-card__row">
                      <span>
                        {a.order_number}
                        {a.need_date && ` · need ${a.need_date}`}
                        {a.promise_date && ` · promised ${a.promise_date}`}
                      </span>
                      <span className={`status-pill status-pill--${a.status}`}>{a.status.replace('_', ' ')}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </section>
    </div>
  )
}

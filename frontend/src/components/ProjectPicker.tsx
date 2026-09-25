import { useProjects } from '../api/hooks'
import { useScope } from '../lib/scope'
import './ProjectPicker.css'

/** Which project Material & Acquisition and Routing show (or every project, in rank order). Lives
 * in those two pages' headers, not the nav: they're the pages it scopes. The choice is app-wide
 * (lib/scope), so Triage's row highlight and the Agent | Journal drawer still follow it. */
export default function ProjectPicker() {
  const { data: projects } = useProjects()
  const { projectId, setProjectId } = useScope()

  return (
    <label className={`project-picker${projectId ? ' project-picker--on' : ''}`}>
      <span className="project-picker__label">Project</span>
      <select value={projectId ?? ''} onChange={(e) => setProjectId(e.target.value || null)}>
        <option value="">All projects</option>
        {projects?.projects.map((p) => (
          <option key={p.depot_project_id} value={p.depot_project_id}>
            #{p.rank} {p.name ?? 'Unknown project'}
          </option>
        ))}
      </select>
    </label>
  )
}

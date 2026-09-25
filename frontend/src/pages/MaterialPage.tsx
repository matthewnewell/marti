import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAcquisition, useProjects } from '../api/hooks'
import AcquisitionTable from '../components/AcquisitionTable'
import ProjectPicker from '../components/ProjectPicker'
import ProjectStrip from '../components/ProjectStrip'
import { useScope } from '../lib/scope'

const OK_STAGES = ['in_stock', 'in_house', 'in_inspection']

/** M & A: every component the builds need, from S4 master through PR, PO, confirmation,
 * receipt and stock. Scoped to the picked project, or every project in rank order. */
export default function MaterialPage() {
  const { projectId } = useScope()
  const { data, isLoading } = useAcquisition(projectId)
  const { data: projects } = useProjects()
  const [problemsOnly, setProblemsOnly] = useState(true)
  const [params] = useSearchParams()
  const focus = params.get('focus')
  const row = projects?.projects.find((p) => p.depot_project_id === projectId)

  const lines = data?.lines ?? []
  const problems = lines.filter((l) => !l.consumed && !OK_STAGES.includes(l.stage))
  const shown = problemsOnly ? problems : lines

  return (
    <div className="page__content">
      <div className="page__head">
        <div>
          <h1>Material &amp; Acquisition</h1>
          <p className="page__sub">
            Every component the builds need: does S4 have a material master, and how far along is its PR → PO → supplier
            confirmation → receipt → stock, dated against when the step that uses it is scheduled to start.
          </p>
        </div>
        <ProjectPicker />
      </div>
      {row && <ProjectStrip row={row} />}

      <div className="toolbar">
        <span className="toolbar__count">
          <strong>{problems.length}</strong> of {lines.length} line{lines.length === 1 ? '' : 's'} not in hand
          {!projectId && ' across all projects'}
        </span>
        <label className="toggle">
          <input type="checkbox" checked={problemsOnly} onChange={(e) => setProblemsOnly(e.target.checked)} />
          Only lines not in hand
        </label>
      </div>

      {isLoading ? (
        <p className="page__empty">Loading…</p>
      ) : shown.length === 0 ? (
        <p className="page__empty">Everything this scope needs is in hand.</p>
      ) : (
        <AcquisitionTable lines={shown} showProject={!projectId} focus={focus} />
      )}
    </div>
  )
}

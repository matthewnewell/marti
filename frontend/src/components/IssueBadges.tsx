import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Issue } from '../api/types'
import { useScope } from '../lib/scope'
import './IssueBadges.css'

const KIND_LABEL: Record<Issue['kind'], (n: number) => string> = {
  short: (n) => `${n} short`,
  held: (n) => `${n} held`,
  quality: (n) => `${n} QN`,
  flag: (n) => `🔥 ${n}`,
}

const KIND_HEADING: Record<Issue['kind'], string> = {
  short: 'Short on material',
  held: 'On MRB hold',
  quality: 'Open quality notifications',
  flag: 'Open hot flags',
}

const LINK_LABEL: Record<Issue['link'], string> = {
  material: 'Show in Material & Acquisition →',
  routing: 'Show in Routing →',
  'hot-flags': 'Open Hot flags →',
}

/** The problem badges on a project (short / held / QN / hot flags). Each one opens a popup of
 * the actual problems: what's wrong, who fixes it and how, and a link straight to it, scoped to
 * the project and focused on that order or material. */
export default function IssueBadges({ projectId, issues }: { projectId: string; issues: Issue[] }) {
  const kinds = (['short', 'held', 'quality', 'flag'] as const).filter((k) => issues.some((i) => i.kind === k))
  if (kinds.length === 0) return null
  return (
    <span className="ib">
      {kinds.map((k) => (
        <IssueBadge key={k} kind={k} projectId={projectId} issues={issues.filter((i) => i.kind === k)} />
      ))}
    </span>
  )
}

function IssueBadge({ kind, projectId, issues }: { kind: Issue['kind']; projectId: string; issues: Issue[] }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  const { setProjectId } = useScope()

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <span className="ib__wrap" ref={ref}>
      <button
        className={`chip ib__chip ib__chip--${kind}`}
        onClick={(e) => {
          e.stopPropagation()
          setOpen(!open)
        }}
        aria-expanded={open}
      >
        {KIND_LABEL[kind](issues.length)}
      </button>
      {open && (
        <div className="ib__pop" role="dialog" onClick={(e) => e.stopPropagation()}>
          <div className="ib__head">{KIND_HEADING[kind]}</div>
          {issues.map((i, n) => (
            <div key={n} className="ib__item">
              <div className="ib__title">{i.title}</div>
              <div className="ib__detail">{i.detail}</div>
              <div className="ib__fix">
                <span className="ib__owner">{i.owner}</span> {i.action}
              </div>
              <Link
                className="ib__link"
                to={i.link === 'hot-flags' ? '/hot-flags' : `/${i.link}${i.focus ? `?focus=${encodeURIComponent(i.focus)}` : ''}`}
                onClick={() => {
                  if (i.link !== 'hot-flags') setProjectId(projectId)
                  setOpen(false)
                }}
              >
                {LINK_LABEL[i.link]}
              </Link>
            </div>
          ))}
        </div>
      )}
    </span>
  )
}

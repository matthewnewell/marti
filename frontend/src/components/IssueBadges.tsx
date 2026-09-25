import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
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

const POP_WIDTH = 380
const POP_MAX_HEIGHT = 360
const GAP = 6
const MARGIN = 8

/** Where the popup goes, in viewport coordinates, next to its chip: below it, or above when
 * there isn't room below and there is more above; kept inside the viewport horizontally. */
function placeNear(chip: DOMRect): CSSProperties {
  const left = Math.max(MARGIN, Math.min(chip.left, window.innerWidth - POP_WIDTH - MARGIN))
  const below = window.innerHeight - chip.bottom - GAP - MARGIN
  const above = chip.top - GAP - MARGIN
  if (below < POP_MAX_HEIGHT && above > below) {
    return { left, bottom: window.innerHeight - chip.top + GAP, maxHeight: Math.min(POP_MAX_HEIGHT, above) }
  }
  return { left, top: chip.bottom + GAP, maxHeight: Math.min(POP_MAX_HEIGHT, Math.max(below, 160)) }
}

function IssueBadge({ kind, projectId, issues }: { kind: Issue['kind']; projectId: string; issues: Issue[] }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  const popRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<CSSProperties | null>(null)
  const { setProjectId } = useScope()

  // The popup renders at the page's top level (a portal), not inside the table: tables here
  // scroll sideways (overflow-x: auto), which also clips anything that hangs below them. So it's
  // positioned against the chip, and follows it when the page scrolls or resizes.
  useLayoutEffect(() => {
    if (!open) return
    const place = () => {
      if (ref.current) setPos(placeNear(ref.current.getBoundingClientRect()))
    }
    place()
    const onScroll = (e: Event) => {
      if (!popRef.current?.contains(e.target as Node)) place()
    }
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', place)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', place)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      const target = e.target as Node
      if (ref.current?.contains(target) || popRef.current?.contains(target)) return
      setOpen(false)
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
      {open && pos && createPortal(
        <div className="ib__pop" role="dialog" ref={popRef} style={pos} onClick={(e) => e.stopPropagation()}>
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
        </div>,
        document.body,
      )}
    </span>
  )
}

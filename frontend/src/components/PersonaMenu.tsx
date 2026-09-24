import { useEffect, useRef, useState } from 'react'
import { usePersona } from '../lib/persona'
import './PersonaMenu.css'

/** The "viewing as" menu, the same one Conway's Depot and Task Master show, rendering the Depot's
 * own persona list (see lib/persona.tsx). Whoever is picked here is who MARTI credits commits,
 * decisions and Journal entries to. If the Depot is unreachable this says so plainly instead of
 * showing an empty menu. */
export default function PersonaMenu() {
  const { persona, people, setPersonId, depotReachable } = usePersona()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!depotReachable) {
    return (
      <div className="persona-menu">
        <span className="persona-menu__trigger persona-menu__trigger--offline" title="Conway's Depot is unreachable — MARTI needs it to know who you are.">
          ⚠ Depot unreachable
        </span>
      </div>
    )
  }

  if (people.length === 0) return null

  return (
    <div className="persona-menu" ref={rootRef}>
      <button
        className="persona-menu__trigger"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Viewing as — a demo persona, not a login"
      >
        <span className="persona-menu__avatar" aria-hidden="true">
          {persona ? persona.name.charAt(0) : '?'}
        </span>
        <span className="persona-menu__id">
          <span className="persona-menu__name">{persona?.name ?? 'Viewing as…'}</span>
          {persona?.title && <span className="persona-menu__role">{persona.title}</span>}
        </span>
        <span className="persona-menu__caret" aria-hidden="true">
          ▾
        </span>
      </button>

      {open && (
        <div className="persona-menu__dropdown" role="menu">
          <p className="persona-menu__hint">
            Same persona list as Conway's Depot — not authentication; nothing here is access-controlled.
          </p>
          {people.map((p) => (
            <button
              key={p.id}
              className={`persona-menu__item ${p.id === persona?.id ? 'persona-menu__item--active' : ''}`}
              role="menuitemradio"
              aria-checked={p.id === persona?.id}
              onClick={() => {
                setPersonId(p.id)
                setOpen(false)
              }}
            >
              <span className="persona-menu__check" aria-hidden="true">
                {p.id === persona?.id ? '✓' : ''}
              </span>
              <span className="persona-menu__item-text">
                <span className="persona-menu__item-name">{p.name}</span>
                <span className="persona-menu__item-title">{p.title}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

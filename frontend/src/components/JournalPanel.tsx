import { useState } from 'react'
import { useAddDepotNote, useDepotJournal } from '../api/hooks'
import './JournalPanel.css'

interface JournalPanelProps {
  depotProjectId: string
}

/**
 * A native React rendering of Conway's Depot's project journal — not the standalone embed
 * widget (backend/embed_assets/journal.js there). That widget renders as an independent
 * floating overlay (its own toggle button, its own fixed-position drawer) by design, so it
 * works in a host with no panel system of its own (Task Master). MARTI already has a real
 * docked panel (AppLayout's shared Agent/Journal tab rail), so embedding the floating widget
 * inside it would mean two overlapping drawer mechanisms — this calls the same Depot REST
 * endpoints (`GET/POST /api/projects/<id>/notes`, `GET /api/projects/<id>/journal`) directly
 * instead, styled to match AgentPanel. Same data, same shared feed — just a different renderer
 * for a host that already has somewhere for it to live.
 */
export default function JournalPanel({ depotProjectId }: JournalPanelProps) {
  const { data: entries, isLoading } = useDepotJournal(depotProjectId)
  const addNote = useAddDepotNote(depotProjectId)
  const [text, setText] = useState('')

  function submit() {
    const body = text.trim()
    if (!body) return
    addNote.mutate(body, { onSuccess: () => setText('') })
  }

  return (
    <div className="journal-panel">
      <div className="journal-panel__list">
        {isLoading ? (
          <p className="journal-panel__empty">Loading…</p>
        ) : !entries || entries.length === 0 ? (
          <p className="journal-panel__empty">Nothing logged yet for this project.</p>
        ) : (
          entries.map((e) => (
            <div key={e.id} className="journal-panel__entry">
              <div className="journal-panel__entry-meta">
                <span>
                  {new Date(e.timestamp).toLocaleString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: 'numeric',
                    minute: '2-digit',
                  })}
                </span>
                {e.author && <span>{e.author}</span>}
                {e.application_name && (
                  <span className="journal-panel__entry-source">{e.application_name}</span>
                )}
              </div>
              {e.href ? (
                <a className="journal-panel__entry-body" href={e.href} target="_blank" rel="noreferrer">
                  {e.summary}
                </a>
              ) : (
                <p className="journal-panel__entry-body">{e.summary}</p>
              )}
            </div>
          ))
        )}
      </div>

      <div className="journal-panel__composer">
        <textarea
          className="journal-panel__input"
          rows={2}
          placeholder="Log a note…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
        />
        <button
          className="journal-panel__submit"
          onClick={submit}
          disabled={!text.trim() || addNote.isPending}
        >
          Add
        </button>
      </div>
    </div>
  )
}

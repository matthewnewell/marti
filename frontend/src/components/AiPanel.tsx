import { useState } from 'react'
import { useAiSuggest } from '../api/hooks'
import './AiPanel.css'

/** "Suggest with AI": leadership's goals in plain language → proposals that show up alongside
 * MARTI's own suggestions, each previewed through the real forecast and committed by a person.
 * The backend endpoint is a stub today and answers "not connected"; the panel is the real one. */
export default function AiPanel({ kind, placeholder }: { kind: 'triage' | 'constraint'; placeholder: string }) {
  const [goals, setGoals] = useState('')
  const ask = useAiSuggest(kind)

  return (
    <div className="ai-panel card">
      <div className="ai-panel__head">
        <span className="ai-panel__spark" aria-hidden="true">
          ✨
        </span>
        <strong>Suggest with AI</strong>
        <span className="ai-panel__tag">Not connected yet</span>
      </div>
      <p className="ai-panel__sub">
        Tell it what matters. The AI turns your goals into rules for MARTI's forecast engine and explains the result.
        It never commits anything: you preview and commit every suggestion yourself.
      </p>
      <textarea
        className="input ai-panel__goals"
        rows={2}
        value={goals}
        placeholder={placeholder}
        onChange={(e) => setGoals(e.target.value)}
      />
      <div className="ai-panel__actions">
        <button className="mt-btn mt-btn--ghost" disabled={!goals.trim() || ask.isPending} onClick={() => ask.mutate(goals.trim())}>
          {ask.isPending ? 'Asking…' : 'Suggest'}
        </button>
      </div>
      {ask.data && <p className="ai-panel__msg">{ask.data.message}</p>}
      {ask.error && <p className="ai-panel__msg ai-panel__msg--err">{ask.error.message}</p>}
    </div>
  )
}

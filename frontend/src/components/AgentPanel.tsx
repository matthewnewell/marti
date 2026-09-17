import { useRef, useState } from 'react'
import { useProjectChat } from '../api/hooks'
import type { ChatMessage } from '../api/types'
import './AgentPanel.css'

interface AgentPanelProps {
  depotProjectId: string
  aiConfigured: boolean
}

const STARTER_PROMPTS = [
  'What needs my attention on this project?',
  'Why is this flagged as at-risk?',
  "What's the status of open acquisition orders?",
]

/** Conversation history is plain React state — nothing persisted to the backend. Refreshing
 * the page loses it, same deliberate v1 scope as Value Stream's own MapChatPanel (a
 * working-session tool, not a permanent record). No header — hosted inside AppLayout's shared
 * tab rail, which is the only chrome. */
export default function AgentPanel({ depotProjectId, aiConfigured }: AgentPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const chat = useProjectChat(depotProjectId)
  const listRef = useRef<HTMLDivElement>(null)

  function scrollToBottom() {
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
    })
  }

  function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || chat.isPending) return

    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: trimmed }]
    setMessages(nextMessages)
    setInput('')
    setError(null)
    scrollToBottom()

    chat.mutate(nextMessages, {
      onSuccess: (result) => {
        if (result.error) {
          setError(result.error)
          return
        }
        setMessages((m) => [...m, { role: 'assistant', content: result.reply ?? '' }])
        scrollToBottom()
      },
      onError: (err) => setError(err instanceof Error ? err.message : 'Something went wrong'),
    })
  }

  if (!aiConfigured) {
    return (
      <div className="agent-panel agent-panel--empty">
        <div className="agent-panel__not-configured">
          AI is not configured for this instance. Set <code>AI_PROVIDER</code> to{' '}
          <code>claude</code>, <code>gemini</code>, <code>ollama</code>, or <code>depot</code> to
          talk through this project's materials, acquisition status, routings, and Tension/
          Impact. Everything else works fully without it.
        </div>
      </div>
    )
  }

  return (
    <div className="agent-panel">
      <div className="agent-panel__messages" ref={listRef}>
        {messages.length === 0 && (
          <div className="agent-panel__intro">
            <p>Ask about this project's materials, acquisition status, routings, or why it's flagged.</p>
            <div className="agent-panel__starters">
              {STARTER_PROMPTS.map((p) => (
                <button key={p} className="agent-panel__starter" onClick={() => send(p)}>
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`agent-panel__msg agent-panel__msg--${m.role}`}>
            {m.content}
          </div>
        ))}

        {chat.isPending && (
          <div className="agent-panel__msg agent-panel__msg--assistant agent-panel__msg--pending">
            thinking…
          </div>
        )}

        {error && <div className="agent-panel__error">{error}</div>}
      </div>

      <form
        className="agent-panel__input-row"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <textarea
          className="agent-panel__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send(input)
            }
          }}
          placeholder="Ask a question…"
          rows={2}
        />
        <button type="submit" className="agent-panel__send" disabled={!input.trim() || chat.isPending}>
          Send
        </button>
      </form>
    </div>
  )
}

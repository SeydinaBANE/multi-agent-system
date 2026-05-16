'use client'

import { useState } from 'react'
import type { Run } from '@/app/page'
import DocumentUpload from './DocumentUpload'

function fmt(iso: string) {
  return new Date(iso).toLocaleString('fr', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

export default function Sidebar({
  sessionId,
  onSessionChange,
  onLoadHistory,
  history,
  onShowRun,
  apiBase,
}: {
  sessionId:       string
  onSessionChange: (id: string) => void
  onLoadHistory:   () => void
  history:         Run[]
  onShowRun:       (run: Run) => void
  apiBase:         string
}) {
  const [input, setInput] = useState(sessionId)

  function applySession() {
    const sid = input.trim() || 'session-1'
    onSessionChange(sid)
  }

  return (
    <aside className="w-64 flex-shrink-0 bg-surface border-r border-border flex flex-col overflow-y-auto">

      {/* Session */}
      <section className="p-4 border-b border-border">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted mb-2.5">Session</p>
        <div className="flex gap-1.5">
          <input
            className="flex-1 bg-bg border border-border rounded-lg text-text text-xs px-2.5 py-1.5 outline-none focus:border-accent min-w-0"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && applySession()}
            placeholder="session-id"
          />
          <button
            onClick={onLoadHistory}
            title="Charger l'historique"
            className="px-2 py-1.5 border border-border rounded-lg text-muted text-xs hover:border-accent hover:text-accent transition-colors"
          >
            📋
          </button>
        </div>
      </section>

      {/* Document ingestion */}
      <section className="p-4 border-b border-border">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted mb-2.5">Ingérer un document</p>
        <DocumentUpload apiBase={apiBase} />
      </section>

      {/* History */}
      <section className="p-4 flex-1">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted mb-2.5">
          Historique <span className="normal-case tracking-normal font-normal">— {sessionId}</span>
        </p>
        {history.length === 0 ? (
          <p className="text-xs text-muted">Lance un run pour voir l&apos;historique.</p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {history.map(run => (
              <button
                key={run.id}
                onClick={() => onShowRun(run)}
                className="w-full text-left px-2.5 py-2 rounded-lg border border-border hover:bg-surface2 transition-colors"
              >
                <p className="text-xs text-text truncate">{run.task}</p>
                <p className="text-[10px] text-muted mt-0.5">{run.iterations} iter · {fmt(run.created_at)}</p>
              </button>
            ))}
          </div>
        )}
      </section>

    </aside>
  )
}

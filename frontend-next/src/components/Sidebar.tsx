'use client'

import { useState } from 'react'
import type { Run } from '@/app/page'
import DocumentUpload from './DocumentUpload'

function fmt(iso: string) {
  return new Date(iso).toLocaleString('fr', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted mb-3">
      {children}
    </p>
  )
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
      <section className="p-5 border-b border-border">
        <SectionTitle>Session</SectionTitle>
        <div className="flex gap-1.5">
          <input
            className="flex-1 bg-bg border border-border rounded-xl text-text text-xs px-3 py-2 outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/20 transition-all min-w-0 placeholder:text-muted"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && applySession()}
            placeholder="session-id"
          />
          <button
            onClick={onLoadHistory}
            title="Charger l'historique"
            className="w-8 h-8 border border-border rounded-xl text-muted hover:border-accent/60 hover:text-accent transition-all flex items-center justify-center flex-shrink-0"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14">
              <path d="M7 1v6l3 3M13 7A6 6 0 1 1 1 7a6 6 0 0 1 12 0z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      </section>

      {/* Document ingestion */}
      <section className="p-5 border-b border-border">
        <SectionTitle>Ingérer un document</SectionTitle>
        <DocumentUpload apiBase={apiBase} />
      </section>

      {/* History */}
      <section className="p-5 flex-1">
        <SectionTitle>
          Historique <span className="normal-case tracking-normal font-normal opacity-60">— {sessionId}</span>
        </SectionTitle>
        {history.length === 0 ? (
          <p className="text-xs text-muted leading-relaxed">Lance un run pour voir l&apos;historique.</p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {history.map(run => (
              <button
                key={run.id}
                onClick={() => onShowRun(run)}
                className="w-full text-left px-3 py-2.5 rounded-xl border border-border hover:bg-surface2 hover:border-border/80 transition-all group"
              >
                <p className="text-xs text-text truncate group-hover:text-accent transition-colors">{run.task}</p>
                <p className="text-[10px] text-muted mt-0.5">{run.iterations} iter · {fmt(run.created_at)}</p>
              </button>
            ))}
          </div>
        )}
      </section>

    </aside>
  )
}

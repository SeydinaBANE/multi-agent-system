'use client'

import { useEffect, useRef, useState } from 'react'
import type { Message } from '@/app/page'

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse self-end max-w-[75%]' : 'max-w-[80%]'}`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-xl flex-shrink-0 flex items-center justify-center text-xs font-bold border ${
        isUser
          ? 'bg-accent border-accent/60 text-white shadow-glow-sm'
          : 'bg-surface2 border-border text-muted'
      }`}>
        {isUser ? 'U' : '🤖'}
      </div>

      {/* Bubble */}
      <div className={`rounded-2xl px-4 py-3 text-sm leading-7 whitespace-pre-wrap break-words ${
        isUser
          ? 'bg-accent rounded-tr-sm text-white shadow-glow-accent'
          : 'bg-surface2 border border-border rounded-tl-sm text-text border-l-2 border-l-accent/30'
      } ${msg.streaming ? 'streaming-cursor' : ''}`}>
        {msg.content || (msg.streaming ? '' : '—')}
      </div>
    </div>
  )
}

export default function ChatArea({
  messages,
  busy,
  connected,
  onSend,
}: {
  messages: Message[]
  busy: boolean
  connected: boolean
  onSend: (task: string) => void
}) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const task = input.trim()
    if (!task || busy) return
    onSend(task)
    setInput('')
  }

  return (
    <>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-8 flex flex-col gap-5">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-surface2 border border-border flex items-center justify-center text-3xl shadow-glow-sm">
              🤖
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text mb-1">Multi-Agent System</h2>
              <p className="text-sm text-muted max-w-xs leading-relaxed">
                Pose une question complexe — le pipeline planifie, recherche, évalue et rédige une réponse structurée.
              </p>
            </div>
            <div className="flex gap-2 mt-2 flex-wrap justify-center">
              {['Analyse le RAG vs fine-tuning', 'Rédige un rapport sur LangGraph', 'Explique les agents LLM'].map(s => (
                <button
                  key={s}
                  onClick={() => { onSend(s) }}
                  disabled={busy || !connected}
                  className="text-xs px-3 py-1.5 rounded-full border border-border text-muted hover:border-accent hover:text-accent transition-colors disabled:opacity-30"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map(m => <MessageBubble key={m.id} msg={m} />)
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-5 py-4 bg-surface border-t border-border flex-shrink-0">
        <div className={`flex gap-2.5 items-end bg-bg border rounded-2xl px-4 py-2.5 transition-all duration-200 ${
          connected ? 'border-border focus-within:border-accent/60 focus-within:shadow-glow-sm' : 'border-border opacity-60'
        }`}>
          <textarea
            className="flex-1 bg-transparent text-text text-sm outline-none resize-none leading-relaxed min-h-[24px] max-h-[120px] overflow-y-auto placeholder:text-muted"
            placeholder={connected ? 'Pose ta question… (Entrée pour envoyer)' : 'Connexion en cours…'}
            rows={1}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            disabled={busy || !connected}
          />
          <button
            onClick={submit}
            disabled={busy || !connected || !input.trim()}
            className="flex-shrink-0 w-8 h-8 bg-accent text-white rounded-xl flex items-center justify-center transition-all hover:opacity-85 disabled:opacity-30 disabled:cursor-not-allowed shadow-glow-sm"
            title="Envoyer"
          >
            {busy ? (
              <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14">
                <path d="M1 7h12M8 2l5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </button>
        </div>
        <p className="text-[10px] text-muted mt-1.5 text-center">Shift+Entrée pour sauter une ligne</p>
      </div>
    </>
  )
}

'use client'

import { useEffect, useRef, useState } from 'react'
import type { Message } from '@/app/page'

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse self-end max-w-[72%]' : 'max-w-[78%]'}`}>
      <div className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center text-sm border border-border bg-surface ${isUser ? '!bg-accent !border-accent' : ''}`}>
        {isUser ? '👤' : '🤖'}
      </div>
      <div className={`rounded-xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words border
        ${isUser
          ? 'bg-accent border-accent rounded-tr-sm'
          : 'bg-surface border-border'
        }
        ${msg.streaming ? 'streaming-cursor' : ''}
      `}>
        {msg.content}
      </div>
    </div>
  )
}

export default function ChatArea({
  messages,
  busy,
  onSend,
}: {
  messages: Message[]
  busy: boolean
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
      <div className="flex-1 overflow-y-auto px-5 py-6 flex flex-col gap-4">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 text-muted">
            <h2 className="text-xl font-semibold text-text">Bonjour 👋</h2>
            <p className="text-sm max-w-sm leading-relaxed">
              Pose une question — le pipeline va planifier, rechercher, évaluer et rédiger une réponse.
            </p>
          </div>
        ) : (
          messages.map(m => <MessageBubble key={m.id} msg={m} />)
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2.5 items-end px-5 py-3.5 bg-surface border-t border-border flex-shrink-0">
        <textarea
          className="flex-1 bg-bg border border-border rounded-lg text-text text-sm px-3 py-2.5 outline-none focus:border-accent resize-none leading-relaxed min-h-[42px] max-h-[110px] overflow-y-auto transition-colors"
          placeholder="Pose ta question… (Entrée pour envoyer, Shift+Entrée pour sauter une ligne)"
          rows={1}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          disabled={busy}
        />
        <button
          onClick={submit}
          disabled={busy || !input.trim()}
          className="h-[42px] px-4 bg-accent text-white rounded-lg text-sm font-medium whitespace-nowrap transition-opacity hover:opacity-85 disabled:opacity-35 disabled:cursor-not-allowed"
        >
          {busy ? '…' : 'Envoyer →'}
        </button>
      </div>
    </>
  )
}

'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import ChatArea from '@/components/ChatArea'
import Pipeline from '@/components/Pipeline'
import Sidebar from '@/components/Sidebar'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const WS_BASE  = API_BASE.replace(/^http/, 'ws')
const API_KEY  = process.env.NEXT_PUBLIC_API_KEY ?? ''

export type PipelineStatus = 'idle' | 'running' | 'done'
export type AgentName = 'planner' | 'researcher' | 'critic' | 'writer'

export interface Message {
  id:        string
  role:      'user' | 'bot'
  content:   string
  streaming: boolean
}

export interface Run {
  id:           number
  task:         string
  final_answer: string | null
  iterations:   number
  created_at:   string
}

const INITIAL_PIPELINE: Record<AgentName, PipelineStatus> = {
  planner: 'idle', researcher: 'idle', critic: 'idle', writer: 'idle',
}

function uid() { return Math.random().toString(36).slice(2) }

export default function Home() {
  const [sessionId,    setSessionId]    = useState('session-1')
  const [messages,     setMessages]     = useState<Message[]>([])
  const [pipeline,     setPipeline]     = useState(INITIAL_PIPELINE)
  const [pipelineMode, setPipelineMode] = useState(true)   // false = chat direct
  const [connected,    setConnected]    = useState(false)
  const [busy,         setBusy]         = useState(false)
  const [history,      setHistory]      = useState<Run[]>([])

  const wsRef        = useRef<WebSocket | null>(null)
  const streamingId  = useRef<string | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>()
  const sessionRef   = useRef(sessionId)
  sessionRef.current = sessionId

  // ── WebSocket ──────────────────────────────────────────────────────────────

  const handleWsMessage = useCallback((raw: string) => {
    const payload = JSON.parse(raw) as Record<string, string>
    const { type, agent, content, detail, mode } = payload

    if (type === 'mode') {
      setPipelineMode(mode === 'pipeline')
      return
    }
    if (type === 'agent_start') {
      setPipeline(p => ({ ...p, [agent as AgentName]: 'running' }))
    } else if (type === 'agent_done') {
      setPipeline(p => ({ ...p, [agent as AgentName]: 'done' }))
    } else if (type === 'token') {
      setMessages(prev => prev.map(m =>
        m.id === streamingId.current ? { ...m, content: m.content + content } : m
      ))
    } else if (type === 'done') {
      setMessages(prev => prev.map(m =>
        m.id === streamingId.current ? { ...m, streaming: false } : m
      ))
      streamingId.current = null
      setBusy(false)
      loadHistory(sessionRef.current)
    } else if (type === 'error') {
      setMessages(prev => prev.map(m =>
        m.id === streamingId.current
          ? { ...m, content: `Erreur : ${detail}`, streaming: false }
          : m
      ))
      streamingId.current = null
      setBusy(false)
    }
  }, [])

  const connect = useCallback(() => {
    wsRef.current?.close()  // ferme l'ancien WS avant d'en créer un nouveau
    const ws = new WebSocket(`${WS_BASE}/ws/run`)
    ws.onopen  = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      reconnectRef.current = setTimeout(connect, 3000)
    }
    ws.onerror  = () => ws.close()
    ws.onmessage = e => handleWsMessage(e.data)
    wsRef.current = ws
  }, [handleWsMessage])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [])  // [] — connexion unique au montage, la reconnexion est gérée par onclose

  // ── Send ───────────────────────────────────────────────────────────────────

  const send = useCallback((task: string) => {
    const ws = wsRef.current
    if (!task.trim() || busy || !ws || ws.readyState !== WebSocket.OPEN) return

    const botId = uid()
    streamingId.current = botId
    setBusy(true)
    setPipeline(INITIAL_PIPELINE)
    setPipelineMode(true)

    setMessages(prev => [
      ...prev,
      { id: uid(), role: 'user', content: task, streaming: false },
      { id: botId, role: 'bot',  content: '',   streaming: true  },
    ])

    ws.send(JSON.stringify({ task, session_id: sessionRef.current, token: API_KEY }))
  }, [busy])

  // ── History ────────────────────────────────────────────────────────────────

  const loadHistory = useCallback(async (sid: string) => {
    try {
      const headers: Record<string, string> = API_KEY ? { 'Authorization': `Bearer ${API_KEY}` } : {}
      const r = await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sid)}/runs`, { headers })
      if (!r.ok) { setHistory([]); return }
      const data = await r.json()
      setHistory(data.runs ?? [])
    } catch { setHistory([]) }
  }, [])

  const showRun = useCallback((run: Run) => {
    setMessages(prev => [
      ...prev,
      { id: uid(), role: 'user', content: run.task,               streaming: false },
      { id: uid(), role: 'bot',  content: run.final_answer ?? '', streaming: false },
    ])
  }, [])

  const handleSessionChange = useCallback((sid: string) => {
    setSessionId(sid)
    loadHistory(sid)
  }, [loadHistory])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="flex items-center justify-between px-5 h-[56px] bg-surface border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-accent/15 border border-accent/30 flex items-center justify-center text-base">
            🤖
          </div>
          <span className="text-[15px] font-semibold text-text">Multi-Agent System</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          {(busy || messages.length > 0) && (
            <span className={`px-2.5 py-1 rounded-full border text-[11px] font-medium transition-all ${
              pipelineMode
                ? 'border-accent/40 text-accent bg-accent/10'
                : 'border-success/40 text-success bg-success/10'
            }`}>
              {pipelineMode ? 'Pipeline' : 'Chat'}
            </span>
          )}
          <div className="flex items-center gap-1.5 text-muted">
            <span className={`w-2 h-2 rounded-full transition-all duration-300 ${
              connected ? 'bg-success shadow-glow-success' : 'bg-muted'
            }`} />
            <span className="text-[11px]">{connected ? 'Connecté' : 'Déconnecté'}</span>
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          sessionId={sessionId}
          onSessionChange={handleSessionChange}
          onLoadHistory={() => loadHistory(sessionId)}
          history={history}
          onShowRun={showRun}
          apiBase={API_BASE}
        />
        <main className="flex flex-col flex-1 overflow-hidden">
          <Pipeline pipeline={pipeline} visible={pipelineMode} />
          <ChatArea messages={messages} busy={busy} connected={connected} onSend={send} />
        </main>
      </div>
    </div>
  )
}

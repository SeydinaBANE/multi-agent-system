'use client'

import { useRef, useState } from 'react'

type Tab = 'text' | 'file' | 'url'
type Status = { msg: string; ok: boolean } | null

function Feedback({ status }: { status: Status }) {
  if (!status) return <div className="h-4" />
  return (
    <p className={`text-xs mt-2 flex items-center gap-1.5 ${status.ok ? 'text-success' : 'text-error'}`}>
      <span>{status.ok ? '✓' : '✕'}</span>
      {status.msg}
    </p>
  )
}

export default function DocumentUpload({ apiBase }: { apiBase: string }) {
  const [tab,     setTab]     = useState<Tab>('text')
  const [status,  setStatus]  = useState<Status>(null)
  const [loading, setLoading] = useState(false)

  const [docText, setDocText] = useState('')
  const [docId,   setDocId]   = useState('')

  const [file,     setFile]     = useState<File | null>(null)
  const [fileId,   setFileId]   = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const [url,   setUrl]   = useState('')
  const [urlId, setUrlId] = useState('')

  const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''
  const authHeader = API_KEY ? { 'Authorization': `Bearer ${API_KEY}` } : {}

  async function submitText() {
    if (!docText.trim()) return
    setLoading(true); setStatus(null)
    try {
      const body: Record<string, string> = { text: docText }
      if (docId.trim()) body.id = docId.trim()
      const r = await fetch(`${apiBase}/api/v1/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify(body),
      })
      const d = await r.json()
      if (r.ok) {
        setStatus({ msg: `Indexé — id : ${d.id}  (${d.chars} chars)`, ok: true })
        setDocText(''); setDocId('')
      } else {
        setStatus({ msg: d.detail ?? 'Erreur', ok: false })
      }
    } catch { setStatus({ msg: 'Erreur réseau', ok: false }) }
    finally  { setLoading(false) }
  }

  async function submitFile() {
    if (!file) return
    if (file.size > 50 * 1024 * 1024) {
      setStatus({ msg: 'Fichier trop volumineux (max 50 MB).', ok: false })
      return
    }
    setLoading(true); setStatus(null)
    const form = new FormData()
    form.append('file', file)
    if (fileId.trim()) form.append('doc_id', fileId.trim())
    try {
      const r = await fetch(`${apiBase}/api/v1/documents/upload`, {
        method: 'POST',
        headers: { ...authHeader },
        body: form,
      })
      const d = await r.json()
      if (r.ok) {
        setStatus({ msg: `Indexé — id : ${d.id}  (${d.chars} chars)`, ok: true })
        setFile(null); setFileId('')
        if (inputRef.current) inputRef.current.value = ''
      } else {
        setStatus({ msg: d.detail ?? 'Erreur', ok: false })
      }
    } catch { setStatus({ msg: 'Erreur réseau', ok: false }) }
    finally  { setLoading(false) }
  }

  async function submitUrl() {
    if (!url.trim()) return
    try { new URL(url.trim()) } catch {
      setStatus({ msg: "URL invalide. Exemple : https://example.com/article", ok: false })
      return
    }
    setLoading(true); setStatus(null)
    try {
      const body: Record<string, string> = { url: url.trim() }
      if (urlId.trim()) body.id = urlId.trim()
      const r = await fetch(`${apiBase}/api/v1/documents/url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify(body),
      })
      const d = await r.json()
      if (r.ok) {
        setStatus({ msg: `Indexé — id : ${d.id}  (${d.chars} chars)`, ok: true })
        setUrl(''); setUrlId('')
      } else {
        setStatus({ msg: d.detail ?? 'Erreur', ok: false })
      }
    } catch { setStatus({ msg: 'Erreur réseau', ok: false }) }
    finally  { setLoading(false) }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

  const TABS: { key: Tab; label: string }[] = [
    { key: 'text', label: 'Texte' },
    { key: 'file', label: 'Fichier' },
    { key: 'url',  label: 'URL' },
  ]

  const inputCls = "w-full bg-bg border border-border rounded-xl text-text text-xs px-3 py-2 outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/20 transition-all placeholder:text-muted"
  const btnCls   = "px-3 py-1.5 bg-accent text-white text-xs rounded-xl font-medium disabled:opacity-30 disabled:cursor-not-allowed hover:opacity-85 transition-opacity"

  return (
    <div>
      {/* Tab bar */}
      <div className="flex gap-1 mb-3">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setStatus(null) }}
            className={`flex-1 text-[11px] font-medium py-1.5 rounded-xl transition-all ${
              tab === t.key
                ? 'bg-accent/15 text-accent border border-accent/30'
                : 'text-muted border border-border hover:border-accent/20 hover:text-text'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Text */}
      {tab === 'text' && (
        <div className="flex flex-col gap-2">
          <textarea
            className={`${inputCls} resize-y min-h-[68px]`}
            placeholder="Colle ton texte ici…"
            value={docText}
            onChange={e => setDocText(e.target.value)}
          />
          <div className="flex gap-1.5">
            <input className={`${inputCls} flex-1`} placeholder="id (optionnel)" value={docId} onChange={e => setDocId(e.target.value)} />
            <button onClick={submitText} disabled={loading || !docText.trim()} className={btnCls}>
              {loading ? '…' : 'Indexer'}
            </button>
          </div>
          <Feedback status={status} />
        </div>
      )}

      {/* File */}
      {tab === 'file' && (
        <div className="flex flex-col gap-2">
          <div
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-all text-xs ${
              dragging ? 'border-accent bg-accent/10 text-accent' : 'border-border hover:border-accent/40 hover:bg-surface2'
            }`}
          >
            {file ? (
              <span className="text-text font-medium">{file.name}</span>
            ) : (
              <span className="text-muted">
                Glisse un fichier ici<br />
                <span className="text-[10px]">PDF · DOCX · TXT</span>
              </span>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
              className="hidden"
              onChange={e => e.target.files?.[0] && setFile(e.target.files[0])}
            />
          </div>
          <div className="flex gap-1.5">
            <input className={`${inputCls} flex-1`} placeholder="id (optionnel)" value={fileId} onChange={e => setFileId(e.target.value)} />
            <button onClick={submitFile} disabled={loading || !file} className={btnCls}>
              {loading ? '…' : 'Indexer'}
            </button>
          </div>
          <Feedback status={status} />
        </div>
      )}

      {/* URL */}
      {tab === 'url' && (
        <div className="flex flex-col gap-2">
          <input
            className={inputCls}
            placeholder="https://example.com/article"
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submitUrl()}
          />
          <div className="flex gap-1.5">
            <input className={`${inputCls} flex-1`} placeholder="id (optionnel)" value={urlId} onChange={e => setUrlId(e.target.value)} />
            <button onClick={submitUrl} disabled={loading || !url.trim()} className={btnCls}>
              {loading ? '…' : 'Scraper'}
            </button>
          </div>
          <Feedback status={status} />
        </div>
      )}
    </div>
  )
}

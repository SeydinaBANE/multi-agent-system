import type { AgentName, PipelineStatus } from '@/app/page'

const AGENTS: { key: AgentName; label: string; icon: string }[] = [
  { key: 'planner',    label: 'Planner',    icon: '🗂' },
  { key: 'researcher', label: 'Researcher', icon: '🔍' },
  { key: 'critic',     label: 'Critic',     icon: '⚖️' },
  { key: 'writer',     label: 'Writer',     icon: '✍️' },
]

function stepClass(status: PipelineStatus) {
  if (status === 'running') return 'border-accent/70 text-accent bg-accent/10 shadow-glow-sm ring-1 ring-accent/30'
  if (status === 'done')    return 'border-success/50 text-success bg-success/10'
  return 'border-border text-muted bg-transparent'
}

function Dot({ status }: { status: PipelineStatus }) {
  if (status === 'done') return <span className="text-[10px] leading-none">✓</span>
  return (
    <span className={`w-1.5 h-1.5 rounded-full bg-current flex-shrink-0 ${status === 'running' ? 'animate-pulse-dot' : ''}`} />
  )
}

export default function Pipeline({
  pipeline,
  visible,
}: {
  pipeline: Record<AgentName, PipelineStatus>
  visible: boolean
}) {
  return (
    <div className={`flex items-center gap-2 px-5 py-3 bg-surface border-b border-border overflow-x-auto flex-shrink-0 transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-20 pointer-events-none'}`}>
      {AGENTS.map((agent, i) => (
        <div key={agent.key} className="flex items-center gap-2">
          {i > 0 && (
            <svg className="w-3 h-3 text-border flex-shrink-0" fill="none" viewBox="0 0 12 12">
              <path d="M2 6h8M7 3l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium whitespace-nowrap transition-all duration-200 ${stepClass(pipeline[agent.key])}`}>
            <Dot status={pipeline[agent.key]} />
            <span className="hidden sm:inline">{agent.icon}</span>
            {agent.label}
          </div>
        </div>
      ))}
    </div>
  )
}

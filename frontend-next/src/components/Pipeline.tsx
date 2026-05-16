import type { AgentName, PipelineStatus } from '@/app/page'

const AGENTS: { key: AgentName; label: string }[] = [
  { key: 'planner',    label: 'Planner'    },
  { key: 'researcher', label: 'Researcher' },
  { key: 'critic',     label: 'Critic'     },
  { key: 'writer',     label: 'Writer'     },
]

function stepClass(status: PipelineStatus) {
  if (status === 'running') return 'border-accent text-accent bg-accent/10'
  if (status === 'done')    return 'border-success text-success bg-success/10'
  return 'border-border text-muted'
}

export default function Pipeline({
  pipeline,
  visible,
}: {
  pipeline: Record<AgentName, PipelineStatus>
  visible: boolean
}) {
  return (
    <div className={`flex items-center gap-1 px-5 py-2.5 bg-surface border-b border-border overflow-x-auto flex-shrink-0 transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-30 pointer-events-none'}`}>
      {AGENTS.map((agent, i) => (
        <div key={agent.key} className="flex items-center gap-1">
          {i > 0 && <span className="text-border text-sm select-none">→</span>}
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-medium whitespace-nowrap transition-all duration-200 ${stepClass(pipeline[agent.key])}`}>
            <span className={`w-1.5 h-1.5 rounded-full bg-current ${pipeline[agent.key] === 'running' ? 'animate-pulse-dot' : ''}`} />
            {agent.label}
          </div>
        </div>
      ))}
    </div>
  )
}

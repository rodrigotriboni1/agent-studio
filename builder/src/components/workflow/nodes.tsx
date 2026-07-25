import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import { Bot, GitBranch, UserCheck, Play, Flag } from 'lucide-react'
import { cn } from '@/lib/utils'

export type WorkflowNodeKind = 'start' | 'agent' | 'condition' | 'human_approval' | 'end'

export interface WorkflowNodeData extends Record<string, unknown> {
  label: string
  agentId?: string
  condition?: string
}

export type WorkflowNode = Node<WorkflowNodeData, WorkflowNodeKind>

const handleClass = '!h-3 !w-3 !border-2 !border-background !bg-primary'

function Shell({
  selected,
  accent,
  children,
}: {
  selected?: boolean
  accent: string
  children: React.ReactNode
}) {
  return (
    <div
      className={cn(
        'min-w-[168px] rounded-xl border bg-card shadow-sm transition-shadow',
        selected ? 'border-primary ring-2 ring-primary/30' : 'border-border hover:shadow-md',
      )}
    >
      <div className={cn('h-1.5 w-full rounded-t-xl', accent)} />
      <div className="flex items-center gap-2.5 px-3 py-2.5">{children}</div>
    </div>
  )
}

export function StartNode({ selected }: NodeProps<WorkflowNode>) {
  return (
    <Shell selected={selected} accent="bg-emerald-500">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
        <Play className="h-4 w-4" />
      </div>
      <div className="text-sm font-semibold">Start</div>
      <Handle type="source" position={Position.Right} className={handleClass} />
    </Shell>
  )
}

export function AgentNode({ data, selected }: NodeProps<WorkflowNode>) {
  return (
    <Shell selected={selected} accent="bg-indigo-500">
      <Handle type="target" position={Position.Left} className={handleClass} />
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
        <Bot className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold">{data.label}</div>
        <div className="truncate text-[11px] text-muted-foreground">
          {data.agentId ? `agent · ${data.agentId}` : 'no agent selected'}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className={handleClass} />
    </Shell>
  )
}

export function ConditionNode({ data, selected }: NodeProps<WorkflowNode>) {
  return (
    <Shell selected={selected} accent="bg-amber-500">
      <Handle type="target" position={Position.Left} className={handleClass} />
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
        <GitBranch className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold">{data.label}</div>
        <div className="truncate font-mono text-[11px] text-muted-foreground">
          {data.condition || 'expression…'}
        </div>
      </div>
      <Handle type="source" position={Position.Right} id="true" style={{ top: '35%' }} className={handleClass} />
      <Handle type="source" position={Position.Right} id="false" style={{ top: '65%' }} className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground" />
    </Shell>
  )
}

export function HumanApprovalNode({ data, selected }: NodeProps<WorkflowNode>) {
  return (
    <Shell selected={selected} accent="bg-rose-500">
      <Handle type="target" position={Position.Left} className={handleClass} />
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-100 text-rose-700">
        <UserCheck className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold">{data.label}</div>
        <div className="truncate text-[11px] text-muted-foreground">human-in-the-loop</div>
      </div>
      <Handle type="source" position={Position.Right} className={handleClass} />
    </Shell>
  )
}

export function EndNode({ selected }: NodeProps<WorkflowNode>) {
  return (
    <Shell selected={selected} accent="bg-slate-500">
      <Handle type="target" position={Position.Left} className={handleClass} />
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
        <Flag className="h-4 w-4" />
      </div>
      <div className="text-sm font-semibold">End</div>
    </Shell>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const nodeTypes = {
  start: StartNode,
  agent: AgentNode,
  condition: ConditionNode,
  human_approval: HumanApprovalNode,
  end: EndNode,
}

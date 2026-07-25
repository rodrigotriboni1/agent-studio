import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Connection,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  Bot,
  GitBranch,
  UserCheck,
  Play,
  Save,
  Trash2,
  CheckCircle,
  XCircle,
  Clock,
  X,
} from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { nodeTypes, type WorkflowNode, type WorkflowNodeKind } from '@/components/workflow/nodes'
import { listAgents, runWorkflow, resumeWorkflow } from '@/lib/api'
import type { AgentManifest, WorkflowRun } from '@/lib/types'

let idCounter = 100
const nextId = (prefix: string) => `${prefix}_${idCounter++}`

const initialNodes: WorkflowNode[] = [
  { id: 'start', type: 'start', position: { x: 40, y: 180 }, data: { label: 'Start' } },
  { id: 'triage', type: 'agent', position: { x: 280, y: 160 }, data: { label: 'Triage', agentId: 'agent-001' } },
  { id: 'review', type: 'human_approval', position: { x: 540, y: 160 }, data: { label: 'Human review' } },
  { id: 'specialist', type: 'agent', position: { x: 800, y: 160 }, data: { label: 'Specialist', agentId: 'agent-002' } },
  { id: 'end', type: 'end', position: { x: 1060, y: 180 }, data: { label: 'End' } },
]

const edgeStyle = { markerEnd: { type: MarkerType.ArrowClosed }, style: { strokeWidth: 2 } }
const initialEdges: Edge[] = [
  { id: 'e1', source: 'start', target: 'triage', ...edgeStyle },
  { id: 'e2', source: 'triage', target: 'review', ...edgeStyle },
  { id: 'e3', source: 'review', target: 'specialist', ...edgeStyle },
  { id: 'e4', source: 'specialist', target: 'end', ...edgeStyle },
]

const PALETTE: { kind: WorkflowNodeKind; label: string; icon: typeof Bot }[] = [
  { kind: 'agent', label: 'Agent', icon: Bot },
  { kind: 'condition', label: 'Condition', icon: GitBranch },
  { kind: 'human_approval', label: 'Human approval', icon: UserCheck },
]

function statusMeta(status: WorkflowRun['status']) {
  const map: Record<WorkflowRun['status'], { cls: string; icon: React.ReactNode }> = {
    RUNNING: { cls: 'bg-secondary text-secondary-foreground', icon: <Clock className="h-3 w-3" /> },
    WAITING_APPROVAL: { cls: 'bg-warning/15 text-amber-700', icon: <Clock className="h-3 w-3" /> },
    COMPLETED: { cls: 'bg-success/15 text-emerald-700', icon: <CheckCircle className="h-3 w-3" /> },
    REJECTED: { cls: 'bg-destructive/15 text-destructive', icon: <XCircle className="h-3 w-3" /> },
    FAILED: { cls: 'bg-destructive/15 text-destructive', icon: <XCircle className="h-3 w-3" /> },
  }
  return map[status]
}

function BuilderInner() {
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNode>(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initialEdges)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [agents, setAgents] = useState<AgentManifest[]>([])
  const [run, setRun] = useState<WorkflowRun | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void listAgents().then(setAgents).catch(() => setAgents([]))
  }, [])

  const onConnect = useCallback(
    (c: Connection) => setEdges((eds) => addEdge({ ...c, ...edgeStyle }, eds)),
    [setEdges],
  )

  const selected = useMemo(() => nodes.find((n) => n.id === selectedId) ?? null, [nodes, selectedId])

  function addNode(kind: WorkflowNodeKind) {
    const id = nextId(kind)
    const label = kind === 'human_approval' ? 'Approval' : kind[0].toUpperCase() + kind.slice(1)
    setNodes((ns) => [
      ...ns,
      { id, type: kind, position: { x: 320 + Math.random() * 240, y: 320 + Math.random() * 80 }, data: { label } },
    ])
    setSelectedId(id)
  }

  function patchSelected(patch: Partial<WorkflowNode['data']>) {
    if (!selectedId) return
    setNodes((ns) => ns.map((n) => (n.id === selectedId ? { ...n, data: { ...n.data, ...patch } } : n)))
  }

  function deleteSelected() {
    if (!selectedId || selectedId === 'start' || selectedId === 'end') return
    setNodes((ns) => ns.filter((n) => n.id !== selectedId))
    setEdges((es) => es.filter((e) => e.source !== selectedId && e.target !== selectedId))
    setSelectedId(null)
  }

  function serialize() {
    const stepKinds = new Set(['agent', 'condition', 'human_approval'])
    const steps = nodes
      .filter((n) => stepKinds.has(n.type ?? ''))
      .map((n) => ({
        id: n.id,
        type: n.type as 'agent' | 'condition' | 'human_approval',
        ...(n.type === 'agent' ? { agent_id: n.data.agentId } : {}),
        ...(n.type === 'condition' ? { condition: n.data.condition } : {}),
      }))
    const defEdges = edges.map((e) => ({
      from: e.source,
      to: e.target,
      ...(e.sourceHandle ? { condition: e.sourceHandle } : {}),
    }))
    return { steps, edges: defEdges }
  }

  async function handleRun() {
    setBusy(true)
    setError(null)
    setRun(null)
    try {
      setRun(await runWorkflow({ definition: serialize() }))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleResume(approval: boolean) {
    if (!run) return
    setBusy(true)
    try {
      setRun(await resumeWorkflow(run.run_id, { approval }))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  function save() {
    localStorage.setItem('agent-studio:workflow', JSON.stringify({ nodes, edges }))
    setError(null)
  }

  return (
    <div>
      <PageHeader
        title="Workflow builder"
        description="Drag to arrange, connect the dots. Nodes map 1:1 to the governed workflow engine."
        actions={
          <>
            <Button variant="outline" onClick={save}>
              <Save className="mr-2 h-4 w-4" /> Save
            </Button>
            <Button onClick={() => void handleRun()} disabled={busy}>
              <Play className="mr-2 h-4 w-4" /> {busy ? 'Running…' : 'Run'}
            </Button>
          </>
        }
      />

      {error && (
        <div className="mb-4 rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex gap-4">
        {/* Canvas */}
        <div className="h-[62vh] flex-1 overflow-hidden rounded-xl border border-border bg-card">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, n) => setSelectedId(n.id)}
            onPaneClick={() => setSelectedId(null)}
            nodeTypes={nodeTypes}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={18} size={1} />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable className="!rounded-lg !border !border-border" />
            <Panel position="top-left" className="!m-3 flex gap-2 rounded-lg border border-border bg-card/95 p-1.5 shadow-sm backdrop-blur">
              {PALETTE.map(({ kind, label, icon: Icon }) => (
                <button
                  key={kind}
                  onClick={() => addNode(kind)}
                  className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <Icon className="h-3.5 w-3.5" /> {label}
                </button>
              ))}
            </Panel>
          </ReactFlow>
        </div>

        {/* Inspector */}
        <div className="w-72 shrink-0 rounded-xl border border-border bg-card p-4">
          {selected ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">Node</h3>
                <Badge variant="secondary" className="font-mono text-[10px]">{selected.type}</Badge>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="node-label">Label</Label>
                <Input
                  id="node-label"
                  value={selected.data.label}
                  onChange={(e) => patchSelected({ label: e.target.value })}
                />
              </div>

              {selected.type === 'agent' && (
                <div className="space-y-1.5">
                  <Label htmlFor="node-agent">Agent</Label>
                  <select
                    id="node-agent"
                    value={selected.data.agentId ?? ''}
                    onChange={(e) => patchSelected({ agentId: e.target.value })}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="">— select —</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({a.id})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {selected.type === 'condition' && (
                <div className="space-y-1.5">
                  <Label htmlFor="node-cond">Condition expression</Label>
                  <Input
                    id="node-cond"
                    placeholder="e.g. score > 0.5"
                    value={selected.data.condition ?? ''}
                    onChange={(e) => patchSelected({ condition: e.target.value })}
                  />
                  <p className="text-[11px] text-muted-foreground">Two outputs: true (top) / false (bottom).</p>
                </div>
              )}

              {selected.type === 'human_approval' && (
                <p className="rounded-md bg-rose-50 p-2.5 text-[11px] text-rose-700">
                  Pauses the run for a human decision (approve / reject) — durable interrupt.
                </p>
              )}

              {selected.id !== 'start' && selected.id !== 'end' && (
                <Button variant="outline" size="sm" className="w-full text-destructive" onClick={deleteSelected}>
                  <Trash2 className="mr-2 h-3.5 w-3.5" /> Delete node
                </Button>
              )}
            </div>
          ) : (
            <div className="space-y-3 text-sm text-muted-foreground">
              <h3 className="font-semibold text-foreground">Inspector</h3>
              <p>Select a node to configure it, or add one from the palette (top-left of the canvas).</p>
              <ul className="space-y-1.5 text-xs">
                <li className="flex items-center gap-2"><Bot className="h-3.5 w-3.5 text-indigo-600" /> Agent — runs a governed agent</li>
                <li className="flex items-center gap-2"><GitBranch className="h-3.5 w-3.5 text-amber-600" /> Condition — branches true/false</li>
                <li className="flex items-center gap-2"><UserCheck className="h-3.5 w-3.5 text-rose-600" /> Human approval — HITL pause</li>
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Run result */}
      {run && (
        <div className="mt-4 rounded-xl border border-border bg-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold">Run</h3>
              <span className="font-mono text-xs text-muted-foreground">{run.run_id}</span>
              <span className={cnBadge(statusMeta(run.status).cls)}>
                {statusMeta(run.status).icon}
                {run.status}
              </span>
            </div>
            <button onClick={() => setRun(null)} className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>

          {run.status === 'WAITING_APPROVAL' && (
            <div className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm text-amber-800">
                Paused at <span className="font-mono font-semibold">{run.pending_step}</span> — human approval required.
              </p>
              <div className="flex gap-2">
                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => void handleResume(true)} disabled={busy}>
                  <CheckCircle className="mr-1.5 h-4 w-4" /> Approve
                </Button>
                <Button size="sm" variant="destructive" onClick={() => void handleResume(false)} disabled={busy}>
                  <XCircle className="mr-1.5 h-4 w-4" /> Reject
                </Button>
              </div>
            </div>
          )}

          {run.status === 'COMPLETED' && (
            <pre className="overflow-auto rounded-lg bg-emerald-50 p-3 text-xs text-emerald-800">
              {JSON.stringify(run.result ?? { ok: true }, null, 2)}
            </pre>
          )}
          {run.status === 'REJECTED' && (
            <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800">Workflow rejected.</p>
          )}
          {run.status === 'FAILED' && (
            <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800">Failed: {run.error}</p>
          )}
        </div>
      )}
    </div>
  )
}

function cnBadge(cls: string) {
  return `inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`
}

export default function WorkflowBuilderPage() {
  return (
    <ReactFlowProvider>
      <BuilderInner />
    </ReactFlowProvider>
  )
}

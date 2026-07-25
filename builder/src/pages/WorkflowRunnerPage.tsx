import { useState } from 'react'
import { CheckCircle, XCircle, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { runWorkflow, resumeWorkflow } from '@/lib/api'
import type { WorkflowRun } from '@/lib/types'

const DEMO_DEFINITION = {
  steps: [
    { id: 'triage', type: 'agent' as const, agent_id: 'agent-001' },
    { id: 'human_review', type: 'human_approval' as const },
    { id: 'specialist', type: 'agent' as const, agent_id: 'agent-002' },
  ],
  edges: [
    { from: 'triage', to: 'human_review' },
    { from: 'human_review', to: 'specialist' },
  ],
}

function statusBadge(status: WorkflowRun['status']) {
  const variants: Record<WorkflowRun['status'], { variant: 'default' | 'secondary' | 'destructive' | 'outline'; icon: React.ReactNode }> = {
    RUNNING: { variant: 'secondary', icon: <Clock className="h-3 w-3" /> },
    WAITING_APPROVAL: { variant: 'outline', icon: <Clock className="h-3 w-3 text-yellow-500" /> },
    COMPLETED: { variant: 'default', icon: <CheckCircle className="h-3 w-3" /> },
    REJECTED: { variant: 'destructive', icon: <XCircle className="h-3 w-3" /> },
    FAILED: { variant: 'destructive', icon: <XCircle className="h-3 w-3" /> },
  }
  const { variant, icon } = variants[status]
  return (
    <Badge variant={variant} className="flex items-center gap-1">
      {icon}
      {status}
    </Badge>
  )
}

export default function WorkflowRunnerPage() {
  const [run, setRun] = useState<WorkflowRun | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleStart() {
    setLoading(true)
    setError(null)
    setRun(null)
    try {
      const result = await runWorkflow({ definition: DEMO_DEFINITION })
      setRun(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleResume(approval: boolean) {
    if (!run) return
    setLoading(true)
    setError(null)
    try {
      const result = await resumeWorkflow(run.run_id, { approval })
      setRun(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Workflow Runner</h1>
        <p className="text-muted-foreground mt-1">Start a workflow and handle human-in-the-loop approval.</p>
      </div>

      {error && <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">{error}</div>}

      <Card>
        <CardHeader>
          <CardTitle>Demo Workflow: Triage → Human Review → Specialist</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2 items-center flex-wrap">
            {DEMO_DEFINITION.steps.map((step, i) => (
              <div key={step.id} className="flex items-center gap-2">
                <div className="rounded-md border px-3 py-1.5 text-sm">
                  <span className="font-mono">{step.id}</span>
                  <span className="text-muted-foreground ml-1">({step.type})</span>
                </div>
                {i < DEMO_DEFINITION.steps.length - 1 && (
                  <span className="text-muted-foreground">→</span>
                )}
              </div>
            ))}
          </div>

          <Button onClick={() => void handleStart()} disabled={loading}>
            {loading ? 'Starting...' : 'Start Workflow'}
          </Button>
        </CardContent>
      </Card>

      {run && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Run: {run.run_id}</CardTitle>
              {statusBadge(run.status)}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {run.pending_step && (
              <p className="text-sm text-muted-foreground">
                Paused at step: <span className="font-mono font-semibold">{run.pending_step}</span>
              </p>
            )}

            {run.status === 'WAITING_APPROVAL' && (
              <div className="rounded-md border border-yellow-200 bg-yellow-50 p-4 space-y-3">
                <p className="text-sm font-medium text-yellow-800">Human approval required</p>
                <p className="text-xs text-yellow-700">
                  The workflow has paused and is waiting for your decision.
                </p>
                <div className="flex gap-2">
                  <Button
                    onClick={() => void handleResume(true)}
                    disabled={loading}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    <CheckCircle className="mr-2 h-4 w-4" />
                    Approve
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => void handleResume(false)}
                    disabled={loading}
                  >
                    <XCircle className="mr-2 h-4 w-4" />
                    Reject
                  </Button>
                </div>
              </div>
            )}

            {run.status === 'COMPLETED' && (
              <div className="rounded-md border border-green-200 bg-green-50 p-4">
                <p className="text-sm font-medium text-green-800">Workflow completed successfully.</p>
                {run.result && (
                  <pre className="text-xs text-green-700 mt-2 overflow-auto">{JSON.stringify(run.result, null, 2)}</pre>
                )}
              </div>
            )}

            {run.status === 'REJECTED' && (
              <div className="rounded-md border border-red-200 bg-red-50 p-4">
                <p className="text-sm font-medium text-red-800">Workflow was rejected.</p>
              </div>
            )}

            {run.status === 'FAILED' && (
              <div className="rounded-md border border-red-200 bg-red-50 p-4">
                <p className="text-sm font-medium text-red-800">Workflow failed: {run.error}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { getAgent, runAgent } from '@/lib/api'
import type { AgentManifest, RunResult } from '@/lib/types'

export default function RunPanelPage() {
  const { id } = useParams<{ id: string }>()
  const [agent, setAgent] = useState<AgentManifest | null>(null)
  const [message, setMessage] = useState('')
  const [result, setResult] = useState<RunResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    getAgent(id)
      .then(setAgent)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [id])

  async function handleRun() {
    if (!id || !message.trim()) return
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const r = await runAgent(id, { message })
      setResult(r)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link to={`/agents/${id}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Run: {agent?.name ?? id}</h1>
          <p className="text-muted-foreground mt-1 text-sm">Send a message and see the governed result.</p>
        </div>
      </div>

      {error && <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">{error}</div>}

      <Card>
        <CardHeader>
          <CardTitle>Message</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            rows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="What is your refund policy?"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                void handleRun()
              }
            }}
          />
          <Button onClick={() => void handleRun()} disabled={running || !message.trim()}>
            <Send className="mr-2 h-4 w-4" />
            {running ? 'Running...' : 'Send (⌘↵)'}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Answer</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm whitespace-pre-wrap">{result.output}</p>
            </CardContent>
          </Card>

          {result.citations.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Citations</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {result.citations.map((c, i) => (
                  <div key={i} className="text-sm border rounded-md p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs text-muted-foreground">{c.source}</span>
                      {c.score !== undefined && (
                        <Badge variant="secondary">{(c.score * 100).toFixed(0)}%</Badge>
                      )}
                    </div>
                    <p className="text-muted-foreground">{c.text}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {result.tool_calls.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Tool Calls</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {result.tool_calls.map((tc, i) => (
                  <div key={i} className="text-sm border rounded-md p-3">
                    <span className="font-mono font-semibold">{tc.name}</span>
                    <pre className="mt-1 text-xs text-muted-foreground overflow-auto">{JSON.stringify(tc.args, null, 2)}</pre>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {result.denied.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Governance Denials</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {result.denied.map((d) => (
                    <Badge key={d} variant="destructive">{d}</Badge>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  These tools/models were denied by the manifest allow-list at runtime.
                </p>
              </CardContent>
            </Card>
          )}

          <Separator />
        </div>
      )}
    </div>
  )
}

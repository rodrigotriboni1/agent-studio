import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PlusCircle, Bot } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { listAgents } from '@/lib/api'
import type { AgentManifest } from '@/lib/types'

export default function AgentsListPage() {
  const [agents, setAgents] = useState<AgentManifest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <PageHeader
        title="Agents"
        description="Create and manage your governed, MCP-native agents."
        actions={
          <Button asChild>
            <Link to="/agents/new">
              <PlusCircle className="mr-2 h-4 w-4" />
              New Agent
            </Link>
          </Button>
        }
      />

      {loading && <p className="text-muted-foreground">Loading agents...</p>}
      {error && <p className="text-destructive">{error}</p>}

      {!loading && !error && agents.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-muted-foreground">No agents yet. Create your first one!</p>
            <Button asChild className="mt-4">
              <Link to="/agents/new">Create Agent</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {agents.map((agent) => (
          <Card key={agent.id} className="hover:shadow-md transition-shadow">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                    <Bot className="h-4 w-4" />
                  </span>
                  {agent.name}
                </CardTitle>
                <Badge variant={agent.status === 'published' ? 'default' : 'secondary'}>
                  {agent.status}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground line-clamp-2">{agent.description}</p>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-1 text-xs text-muted-foreground mb-4">
                <span>Model: <span className="font-mono">{agent.model}</span></span>
                <span>Version: {agent.version}</span>
                <span>Tools: {agent.allowed_tools.length > 0 ? agent.allowed_tools.join(', ') : 'none'}</span>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/agents/${agent.id}`}>Edit</Link>
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/agents/${agent.id}/run`}>Run</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bot, Workflow, ShieldCheck, GitBranch, ArrowRight, Plus } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { listAgents } from '@/lib/api'
import type { AgentManifest } from '@/lib/types'

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof Bot
  label: string
  value: string | number
  hint: string
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-accent-foreground">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-2xl font-bold leading-none text-foreground">{value}</div>
          <div className="mt-1 text-sm font-medium text-foreground">{label}</div>
          <div className="text-xs text-muted-foreground">{hint}</div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const [agents, setAgents] = useState<AgentManifest[]>([])

  useEffect(() => {
    void listAgents().then(setAgents).catch(() => setAgents([]))
  }, [])

  const published = agents.filter((a) => a.status === 'published').length
  const totalTools = new Set(agents.flatMap((a) => a.allowed_tools)).size

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Your governed, multi-tenant agent platform at a glance."
        actions={
          <Button asChild>
            <Link to="/agents/new">
              <Plus className="mr-2 h-4 w-4" /> New Agent
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Bot} label="Agents" value={agents.length} hint={`${published} published`} />
        <StatCard icon={ShieldCheck} label="Governed tools" value={totalTools} hint="via manifest allow-lists" />
        <StatCard icon={Workflow} label="Workflows" value="—" hint="build visually" />
        <StatCard icon={GitBranch} label="Versioning" value="on" hint="diff + rollback" />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Recent agents</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/agents">
                View all <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {agents.length === 0 && <p className="text-sm text-muted-foreground">No agents yet.</p>}
            {agents.slice(0, 5).map((a) => (
              <Link
                key={a.id}
                to={`/agents/${a.id}`}
                className="flex items-center justify-between rounded-lg border border-transparent px-3 py-2.5 transition-colors hover:border-border hover:bg-muted/50"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-medium">{a.name}</div>
                    <div className="text-xs text-muted-foreground font-mono">{a.model}</div>
                  </div>
                </div>
                <Badge variant={a.status === 'published' ? 'default' : 'secondary'}>{a.status}</Badge>
              </Link>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Quick actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link to="/agents/new">
                <Bot className="mr-2 h-4 w-4" /> Create an agent
              </Link>
            </Button>
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link to="/workflows/new">
                <Workflow className="mr-2 h-4 w-4" /> Build a workflow
              </Link>
            </Button>
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link to="/agents">
                <ShieldCheck className="mr-2 h-4 w-4" /> Review governance
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

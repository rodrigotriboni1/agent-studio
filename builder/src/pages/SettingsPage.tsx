import { Wrench, Cpu, ShieldCheck, Building2 } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const SEAMS = [
  { icon: Wrench, name: 'ToolProvider', now: 'MCP client', later: 'MCP Gateway' },
  { icon: Cpu, name: 'ModelProvider', now: 'LiteLLM (OpenAI-compat)', later: 'LLM Bridge (self-host)' },
  { icon: ShieldCheck, name: 'AuthzProvider', now: 'Manifest allow-lists', later: 'OpenFGA / SpiceDB' },
  { icon: Building2, name: 'TenantContext', now: 'Single default tenant', later: 'Real AuthN' },
]

export default function SettingsPage() {
  return (
    <div>
      <PageHeader
        title="Settings"
        description="The four seams keep agent-studio pluggable into the platform without a rewrite."
      />
      <div className="grid gap-4 sm:grid-cols-2">
        {SEAMS.map(({ icon: Icon, name, now, later }) => (
          <Card key={name}>
            <CardContent className="space-y-3 p-5">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                  <Icon className="h-4 w-4" />
                </div>
                <span className="font-mono text-sm font-semibold">{name}</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Badge variant="default">now</Badge>
                <span className="text-foreground">{now}</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Badge variant="secondary">later</Badge>
                <span className="text-muted-foreground">{later}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

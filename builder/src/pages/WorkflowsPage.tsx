import { Link } from 'react-router-dom'
import { Workflow, Plus, ArrowRight, UserCheck } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const TEMPLATES = [
  {
    id: 'triage-review',
    name: 'Triage → Human review → Specialist',
    description: 'Classic human-in-the-loop: an agent triages, a human approves, a specialist resolves.',
    steps: 3,
    hitl: true,
  },
]

export default function WorkflowsPage() {
  return (
    <div>
      <PageHeader
        title="Workflows"
        description="Compose multi-step, multi-agent graphs with human-in-the-loop, built visually."
        actions={
          <Button asChild>
            <Link to="/workflows/new">
              <Plus className="mr-2 h-4 w-4" /> New Workflow
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {TEMPLATES.map((t) => (
          <Link key={t.id} to="/workflows/new">
            <Card className="group h-full transition-shadow hover:shadow-md">
              <CardContent className="flex h-full flex-col gap-3 p-5">
                <div className="flex items-center justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                    <Workflow className="h-5 w-5" />
                  </div>
                  {t.hitl && (
                    <Badge variant="secondary" className="gap-1">
                      <UserCheck className="h-3 w-3" /> HITL
                    </Badge>
                  )}
                </div>
                <div>
                  <div className="font-semibold">{t.name}</div>
                  <p className="mt-1 text-sm text-muted-foreground">{t.description}</p>
                </div>
                <div className="mt-auto flex items-center justify-between pt-2 text-sm">
                  <span className="text-muted-foreground">{t.steps} steps</span>
                  <span className="flex items-center gap-1 font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                    Open <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}

        <Link to="/workflows/new">
          <Card className="flex h-full items-center justify-center border-dashed transition-colors hover:border-primary hover:bg-accent/40">
            <CardContent className="flex flex-col items-center gap-2 p-8 text-muted-foreground">
              <Plus className="h-6 w-6" />
              <span className="text-sm font-medium">Blank canvas</span>
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  )
}

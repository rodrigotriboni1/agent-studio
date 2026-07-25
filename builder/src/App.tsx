import { Routes, Route, NavLink } from 'react-router-dom'
import AgentsListPage from './pages/AgentsListPage'
import AgentEditorPage from './pages/AgentEditorPage'
import RunPanelPage from './pages/RunPanelPage'
import WorkflowRunnerPage from './pages/WorkflowRunnerPage'

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b border-border bg-card">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center gap-6">
            <span className="font-bold text-foreground">Agent Studio</span>
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `text-sm font-medium transition-colors ${isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'}`
              }
            >
              Agents
            </NavLink>
            <NavLink
              to="/workflows"
              className={({ isActive }) =>
                `text-sm font-medium transition-colors ${isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'}`
              }
            >
              Workflows
            </NavLink>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Routes>
          <Route path="/" element={<AgentsListPage />} />
          <Route path="/agents/new" element={<AgentEditorPage />} />
          <Route path="/agents/:id" element={<AgentEditorPage />} />
          <Route path="/agents/:id/run" element={<RunPanelPage />} />
          <Route path="/workflows" element={<WorkflowRunnerPage />} />
        </Routes>
      </main>
    </div>
  )
}

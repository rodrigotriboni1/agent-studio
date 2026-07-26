import { Routes, Route } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import DashboardPage from './pages/DashboardPage'
import AgentsListPage from './pages/AgentsListPage'
import AgentEditorPage from './pages/AgentEditorPage'
import RunPanelPage from './pages/RunPanelPage'
import WorkflowsPage from './pages/WorkflowsPage'
import WorkflowBuilderPage from './pages/WorkflowBuilderPage'
import SettingsPage from './pages/SettingsPage'
import ChatPage from './pages/ChatPage'
import HistoryPage from './pages/HistoryPage'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/agents" element={<AgentsListPage />} />
        <Route path="/agents/new" element={<AgentEditorPage />} />
        <Route path="/agents/:id" element={<AgentEditorPage />} />
        <Route path="/agents/:id/run" element={<RunPanelPage />} />
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/workflows/new" element={<WorkflowBuilderPage />} />
        <Route path="/workflows/:id" element={<WorkflowBuilderPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/chat/:conversationId" element={<ChatPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/history/:conversationId" element={<HistoryPage />} />
      </Routes>
    </AppShell>
  )
}

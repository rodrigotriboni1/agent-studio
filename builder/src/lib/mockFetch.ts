import type { AgentManifest, RunResult, WorkflowRun } from './types'
import {
  MOCK_AGENTS,
  MOCK_RUN_RESULT,
  MOCK_WORKFLOW_RUN,
  MOCK_VERSIONS,
} from './mocks'

// Simple in-memory store for mock mode
let agents: AgentManifest[] = [...MOCK_AGENTS]

function delay(ms = 300) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function mockFetch(url: string, init?: RequestInit): Promise<Response> {
  await delay()
  const method = init?.method?.toUpperCase() ?? 'GET'
  const body = init?.body ? (JSON.parse(init.body as string) as Record<string, unknown>) : null

  // Strip base URL
  const path = url.replace(/^https?:\/\/[^/]+/, '')

  // Routes
  if (path === '/agents' && method === 'GET') {
    return ok(agents)
  }

  if (path === '/agents' && method === 'POST') {
    const id = `agent-${Date.now()}`
    const newAgent: AgentManifest = {
      id,
      tenant_id: 'default',
      name: (body?.name as string) ?? 'Untitled Agent',
      description: (body?.description as string) ?? '',
      version: 1,
      status: 'draft',
      system_prompt: (body?.system_prompt as string) ?? 'You are a helpful assistant.',
      model: (body?.model as string) ?? 'gpt-4o-mini',
      guardrails: { max_tokens: 2048, temperature: 0.0, max_tool_calls: 8, blocked_keywords: [] },
      memory: { kind: 'none', max_messages: 20 },
      allowed_models: (body?.allowed_models as string[]) ?? [],
      allowed_tools: (body?.allowed_tools as string[]) ?? [],
      rag_sources: [],
      metadata: {},
    }
    agents = [...agents, newAgent]
    return ok(newAgent)
  }

  const agentMatch = path.match(/^\/agents\/([^/]+)$/)
  if (agentMatch) {
    const id = agentMatch[1]
    if (method === 'GET') {
      const agent = agents.find((a) => a.id === id)
      if (!agent) return notFound()
      return ok(agent)
    }
    if (method === 'PUT') {
      const idx = agents.findIndex((a) => a.id === id)
      if (idx < 0) return notFound()
      agents[idx] = { ...agents[idx], ...(body as Partial<AgentManifest>) }
      return ok(agents[idx])
    }
  }

  const publishMatch = path.match(/^\/agents\/([^/]+)\/publish$/)
  if (publishMatch && method === 'POST') {
    const id = publishMatch[1]
    const idx = agents.findIndex((a) => a.id === id)
    if (idx < 0) return notFound()
    agents[idx] = { ...agents[idx], status: 'published', version: agents[idx].version + 1 }
    return ok(agents[idx])
  }

  const versionsMatch = path.match(/^\/agents\/([^/]+)\/versions$/)
  if (versionsMatch && method === 'GET') {
    return ok(MOCK_VERSIONS)
  }

  const rollbackMatch = path.match(/^\/agents\/([^/]+)\/rollback$/)
  if (rollbackMatch && method === 'POST') {
    const id = rollbackMatch[1]
    const agent = agents.find((a) => a.id === id)
    if (!agent) return notFound()
    return ok({ ...agent, version: agent.version + 1, status: 'draft' })
  }

  const runMatch = path.match(/^\/agents\/([^/]+)\/run$/)
  if (runMatch && method === 'POST') {
    const result: RunResult = { ...MOCK_RUN_RESULT }
    return ok(result)
  }

  const ingestMatch = path.match(/^\/sources\/([^/]+)\/ingest$/)
  if (ingestMatch && method === 'POST') {
    return ok({ ingested: 3 })
  }

  if (path === '/workflows/run' && method === 'POST') {
    const wf: WorkflowRun = { ...MOCK_WORKFLOW_RUN, run_id: `wf-${Date.now()}` }
    return ok(wf)
  }

  const resumeMatch = path.match(/^\/workflows\/([^/]+)\/resume$/)
  if (resumeMatch && method === 'POST') {
    const approval = (body?.approval as boolean) ?? true
    const wf: WorkflowRun = {
      run_id: resumeMatch[1],
      status: approval ? 'COMPLETED' : 'REJECTED',
      result: approval ? { message: 'Workflow completed successfully.' } : undefined,
    }
    return ok(wf)
  }

  return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
}

function ok(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function notFound(): Response {
  return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
}

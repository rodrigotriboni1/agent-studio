import type { AgentManifest, RunResult, WorkflowRun, ChatMessage, Conversation, SendChatRequest } from './types'
import {
  MOCK_AGENTS,
  MOCK_RUN_RESULT,
  MOCK_WORKFLOW_RUN,
  MOCK_VERSIONS,
  MOCK_ASSISTANT_MESSAGE,
  MOCK_WORKFLOW_APPROVAL_MESSAGE,
  MOCK_WORKFLOW_COMPLETED_MESSAGE,
  MOCK_WORKFLOW_REJECTED_MESSAGE,
  MOCK_CONVERSATIONS,
  MOCK_CONVERSATION_DETAIL,
} from './mocks'

// Simple in-memory store for mock mode
let agents: AgentManifest[] = [...MOCK_AGENTS]

// In-memory conversation store for mock mode
const conversationStore: Map<string, Conversation> = new Map([
  [MOCK_CONVERSATION_DETAIL.id, { ...MOCK_CONVERSATION_DETAIL }],
])

function delay(ms = 300) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function mockFetch(url: string, init?: RequestInit): Promise<Response> {
  await delay()
  const method = init?.method?.toUpperCase() ?? 'GET'
  const body = init?.body ? (JSON.parse(init.body as string) as Record<string, unknown>) : null

  // Strip base URL
  const path = url.replace(/^https?:\/\/[^/]+/, '')

  // ── Agents ───────────────────────────────────────────────────────────────

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

  // ── Agent chat (non-streaming) ────────────────────────────────────────────

  const agentChatMatch = path.match(/^\/agents\/([^/]+)\/chat$/)
  if (agentChatMatch && method === 'POST') {
    const agentId = agentChatMatch[1]
    const convId = (body?.conversation_id as string | undefined) ?? `conv-${Date.now()}`
    const userMsg: ChatMessage = {
      role: 'user',
      content: (body?.message as string) ?? '',
      ts: new Date().toISOString(),
    }
    const assistantMsg: ChatMessage = { ...MOCK_ASSISTANT_MESSAGE, ts: new Date().toISOString() }

    if (!conversationStore.has(convId)) {
      const agent = agents.find((a) => a.id === agentId)
      conversationStore.set(convId, {
        id: convId,
        tenant_id: 'default',
        agent_id: agentId,
        title: agent ? `Chat with ${agent.name}` : 'New conversation',
        created_at: new Date().toISOString(),
        messages: [],
      })
    }
    const conv = conversationStore.get(convId)!
    conv.messages.push(userMsg, assistantMsg)

    return ok({ conversation_id: convId, message: assistantMsg })
  }

  // ── Ingest ────────────────────────────────────────────────────────────────

  const ingestMatch = path.match(/^\/sources\/([^/]+)\/ingest$/)
  if (ingestMatch && method === 'POST') {
    return ok({ ingested: 3 })
  }

  // ── Workflows ─────────────────────────────────────────────────────────────

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

  // ── Workflow chat ─────────────────────────────────────────────────────────

  if (path === '/workflows/chat' && method === 'POST') {
    const convId = (body?.conversation_id as string | undefined) ?? `conv-wf-${Date.now()}`
    const userMsg: ChatMessage = {
      role: 'user',
      content: (body?.message as string) ?? '',
      ts: new Date().toISOString(),
    }
    const assistantMsg: ChatMessage = { ...MOCK_WORKFLOW_APPROVAL_MESSAGE, ts: new Date().toISOString() }

    if (!conversationStore.has(convId)) {
      conversationStore.set(convId, {
        id: convId,
        tenant_id: 'default',
        title: 'Workflow conversation',
        created_at: new Date().toISOString(),
        messages: [],
      })
    }
    const conv = conversationStore.get(convId)!
    conv.messages.push(userMsg, assistantMsg)

    return ok({ conversation_id: convId, message: assistantMsg })
  }

  // ── Conversations ─────────────────────────────────────────────────────────

  if (path === '/conversations' && method === 'GET') {
    // Merge static mock list with dynamically created conversations
    const dynamic: Omit<Conversation, 'messages'>[] = Array.from(conversationStore.values()).map(
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      ({ messages: _messages, ...rest }) => rest,
    )
    const staticIds = new Set(MOCK_CONVERSATIONS.map((c) => c.id))
    const dynamicNew = dynamic.filter((c) => !staticIds.has(c.id))
    return ok([...MOCK_CONVERSATIONS, ...dynamicNew])
  }

  const convDetailMatch = path.match(/^\/conversations\/([^/]+)$/)
  if (convDetailMatch && method === 'GET') {
    const id = convDetailMatch[1]
    const stored = conversationStore.get(id)
    if (stored) return ok(stored)
    // Return the static mock detail for conv-001
    if (id === MOCK_CONVERSATION_DETAIL.id) return ok(MOCK_CONVERSATION_DETAIL)
    return notFound()
  }

  const convResumeMatch = path.match(/^\/conversations\/([^/]+)\/resume$/)
  if (convResumeMatch && method === 'POST') {
    const convId = convResumeMatch[1]
    const approved = (body?.approved as boolean) ?? true
    const assistantMsg: ChatMessage = approved
      ? { ...MOCK_WORKFLOW_COMPLETED_MESSAGE, ts: new Date().toISOString() }
      : { ...MOCK_WORKFLOW_REJECTED_MESSAGE, ts: new Date().toISOString() }

    const conv = conversationStore.get(convId)
    if (conv) {
      // Mark the pending approval as resolved
      for (const msg of conv.messages) {
        if (msg.approval && !msg.approval.resolved) {
          msg.approval = {
            ...msg.approval,
            resolved: approved ? 'approved' : 'rejected',
          }
        }
      }
      conv.messages.push(assistantMsg)
    }
    return ok({ conversation_id: convId, message: assistantMsg })
  }

  return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
}

// ── Streaming mock ────────────────────────────────────────────────────────────

const STREAMING_TOKENS = [
  'Based ',
  'on our ',
  'knowledge base, ',
  'the refund policy ',
  'allows returns ',
  'within 30 days ',
  'of purchase. ',
  'Please contact ',
  'support@example.com ',
  'with your order number.',
]

export async function mockStreamChat(
  agentId: string,
  req: SendChatRequest,
  onToken: (text: string) => void,
  onDone: (message: ChatMessage) => void,
): Promise<void> {
  const convId = req.conversation_id ?? `conv-${Date.now()}`

  // Simulate streaming tokens with small delays
  for (const token of STREAMING_TOKENS) {
    await delay(60)
    onToken(token)
  }

  const assistantMsg: ChatMessage = { ...MOCK_ASSISTANT_MESSAGE, ts: new Date().toISOString() }
  const userMsg: ChatMessage = {
    role: 'user',
    content: req.message,
    ts: new Date().toISOString(),
  }

  if (!conversationStore.has(convId)) {
    const agentsList = MOCK_AGENTS
    const agent = agentsList.find((a) => a.id === agentId)
    conversationStore.set(convId, {
      id: convId,
      tenant_id: 'default',
      agent_id: agentId,
      title: agent ? `Chat with ${agent.name}` : 'New conversation',
      created_at: new Date().toISOString(),
      messages: [],
    })
  }
  const conv = conversationStore.get(convId)!
  conv.messages.push(userMsg, assistantMsg)

  await delay(100)
  onDone(assistantMsg)
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

import type { AgentManifest, RunResult, WorkflowRun, AgentVersion } from './types'

export const MOCK_AGENTS: AgentManifest[] = [
  {
    id: 'agent-001',
    tenant_id: 'default',
    name: 'Support Bot',
    description: 'Customer support agent with RAG over the knowledge base.',
    version: 3,
    status: 'published',
    system_prompt: 'You are a helpful customer support agent. Always be polite and cite your sources.',
    model: 'gpt-4o-mini',
    guardrails: { max_tokens: 2048, temperature: 0.2, max_tool_calls: 5, blocked_keywords: [] },
    memory: { kind: 'buffer', max_messages: 20 },
    allowed_models: ['gpt-4o', 'gpt-4o-mini'],
    allowed_tools: ['search_kb', 'send_email'],
    rag_sources: [{ name: 'knowledge_base', top_k: 4, rerank: true }],
    metadata: { owner: 'team-support' },
  },
  {
    id: 'agent-002',
    tenant_id: 'default',
    name: 'Code Reviewer',
    description: 'Reviews pull requests and suggests improvements.',
    version: 1,
    status: 'draft',
    system_prompt: 'You are an expert code reviewer. Focus on correctness, performance, and maintainability.',
    model: 'gpt-4o',
    guardrails: { max_tokens: 4096, temperature: 0.0, max_tool_calls: 3, blocked_keywords: [] },
    memory: { kind: 'none', max_messages: 20 },
    allowed_models: ['gpt-4o'],
    allowed_tools: ['read_file', 'list_files'],
    rag_sources: [],
    metadata: {},
  },
]

export const MOCK_RUN_RESULT: RunResult = {
  output: 'Based on our knowledge base, the refund policy allows returns within 30 days of purchase. Please contact support@example.com with your order number.',
  tool_calls: [
    { name: 'search_kb', args: { query: 'refund policy' }, result: 'Returns allowed within 30 days' },
  ],
  citations: [
    { source: 'knowledge_base/policy.pdf', text: 'Returns are accepted within 30 days of purchase date.', score: 0.92 },
  ],
  steps: [],
  denied: ['send_email'],
}

export const MOCK_WORKFLOW_RUN: WorkflowRun = {
  run_id: 'wf-run-001',
  status: 'WAITING_APPROVAL',
  pending_step: 'human_review',
}

export const MOCK_VERSIONS: AgentVersion[] = [
  { version: 3, status: 'published', created_at: '2024-01-15T10:30:00Z' },
  { version: 2, status: 'published', created_at: '2024-01-10T09:00:00Z' },
  { version: 1, status: 'published', created_at: '2024-01-05T08:00:00Z' },
]

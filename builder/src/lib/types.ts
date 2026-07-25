export interface Guardrails {
  max_tokens: number
  temperature: number
  max_tool_calls: number
  system_suffix?: string
  blocked_keywords: string[]
}

export interface MemoryConfig {
  kind: 'none' | 'buffer' | 'summary'
  max_messages: number
}

export interface RagSourceRef {
  name: string
  top_k: number
  rerank: boolean
}

export type ManifestStatus = 'draft' | 'published'

export interface AgentManifest {
  id: string
  tenant_id: string
  name: string
  description: string
  version: number
  status: ManifestStatus
  system_prompt: string
  model: string
  guardrails: Guardrails
  memory: MemoryConfig
  allowed_models: string[]
  allowed_tools: string[]
  rag_sources: RagSourceRef[]
  metadata: Record<string, unknown>
}

export interface RunResult {
  output: string
  tool_calls: Array<{ name: string; args: Record<string, unknown>; result?: unknown }>
  citations: Array<{ source: string; text: string; score?: number }>
  steps: Array<Record<string, unknown>>
  denied: string[]
}

export type WorkflowStatus = 'RUNNING' | 'WAITING_APPROVAL' | 'COMPLETED' | 'REJECTED' | 'FAILED'

export interface WorkflowRun {
  run_id: string
  status: WorkflowStatus
  pending_step?: string
  result?: Record<string, unknown>
  error?: string
}

export interface AgentVersion {
  version: number
  status: ManifestStatus
  created_at: string
}

export interface CreateAgentRequest {
  name: string
  description?: string
  system_prompt?: string
  model?: string
  allowed_tools?: string[]
  allowed_models?: string[]
  rag_sources?: RagSourceRef[]
  guardrails?: Partial<Guardrails>
  memory?: Partial<MemoryConfig>
}

export interface RunRequest {
  message: string
  tenant_id?: string
}

export interface WorkflowRunRequest {
  definition: {
    steps: Array<{ id: string; type: 'agent' | 'condition' | 'human_approval'; agent_id?: string; condition?: string }>
    edges: Array<{ from: string; to: string; condition?: string }>
  }
  input?: Record<string, unknown>
  tenant_id?: string
}

export interface WorkflowResumeRequest {
  approval: boolean
  data?: Record<string, unknown>
}

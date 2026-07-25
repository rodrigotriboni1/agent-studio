import type {
  AgentManifest,
  CreateAgentRequest,
  RunResult,
  RunRequest,
  AgentVersion,
  WorkflowRun,
  WorkflowRunRequest,
  WorkflowResumeRequest,
} from './types'
import { mockFetch } from './mockFetch'

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'
export const USE_MOCKS = (import.meta.env.VITE_USE_MOCKS as string | undefined) !== '0'

let tenantId = 'default'

export function setTenantId(id: string) {
  tenantId = id
}

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const fullUrl = `${BASE_URL}${path}`
  const headers = {
    'Content-Type': 'application/json',
    'X-Tenant-Id': tenantId,
    ...(init?.headers ?? {}),
  }
  const reqInit = { ...init, headers }

  const response = USE_MOCKS
    ? await mockFetch(fullUrl, reqInit)
    : await fetch(fullUrl, reqInit)

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`API error ${response.status}: ${text}`)
  }
  return response.json() as Promise<T>
}

export async function listAgents(): Promise<AgentManifest[]> {
  return fetchApi<AgentManifest[]>('/agents')
}

export async function getAgent(id: string): Promise<AgentManifest> {
  return fetchApi<AgentManifest>(`/agents/${id}`)
}

export async function createAgent(data: CreateAgentRequest): Promise<AgentManifest> {
  return fetchApi<AgentManifest>('/agents', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateAgent(id: string, data: Partial<CreateAgentRequest>): Promise<AgentManifest> {
  return fetchApi<AgentManifest>(`/agents/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function publishAgent(id: string): Promise<AgentManifest> {
  return fetchApi<AgentManifest>(`/agents/${id}/publish`, { method: 'POST' })
}

export async function listVersions(id: string): Promise<AgentVersion[]> {
  return fetchApi<AgentVersion[]>(`/agents/${id}/versions`)
}

export async function rollbackAgent(id: string, version: number): Promise<AgentManifest> {
  return fetchApi<AgentManifest>(`/agents/${id}/rollback`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export async function runAgent(id: string, req: RunRequest): Promise<RunResult> {
  return fetchApi<RunResult>(`/agents/${id}/run`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function ingestSource(
  name: string,
  documents: Array<{ text: string; metadata?: Record<string, unknown> }>,
): Promise<{ ingested: number }> {
  return fetchApi<{ ingested: number }>(`/sources/${name}/ingest`, {
    method: 'POST',
    body: JSON.stringify({ documents }),
  })
}

export async function runWorkflow(req: WorkflowRunRequest): Promise<WorkflowRun> {
  return fetchApi<WorkflowRun>('/workflows/run', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function resumeWorkflow(runId: string, req: WorkflowResumeRequest): Promise<WorkflowRun> {
  return fetchApi<WorkflowRun>(`/workflows/${runId}/resume`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

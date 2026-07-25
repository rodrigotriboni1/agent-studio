import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Plus, X, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import {
  getAgent,
  createAgent,
  updateAgent,
  publishAgent,
  listVersions,
  rollbackAgent,
} from '@/lib/api'
import type { AgentManifest, AgentVersion, RagSourceRef } from '@/lib/types'

const DEFAULT_GUARDRAILS = { max_tokens: 2048, temperature: 0.0, max_tool_calls: 8, blocked_keywords: [] as string[] }

export default function AgentEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isNew = id === undefined || id === 'new'

  const [agent, setAgent] = useState<AgentManifest | null>(null)
  const [versions, setVersions] = useState<AgentVersion[]>([])
  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful assistant.')
  const [model, setModel] = useState('gpt-4o-mini')
  const [allowedTools, setAllowedTools] = useState<string[]>([])
  const [newTool, setNewTool] = useState('')
  const [allowedModels, setAllowedModels] = useState<string[]>([])
  const [newModel, setNewModel] = useState('')
  const [ragSources, setRagSources] = useState<RagSourceRef[]>([])
  const [newSourceName, setNewSourceName] = useState('')
  const [maxTokens, setMaxTokens] = useState(2048)
  const [temperature, setTemperature] = useState(0.0)
  const [maxToolCalls, setMaxToolCalls] = useState(8)

  useEffect(() => {
    if (isNew) return
    const agentId = id!
    Promise.all([getAgent(agentId), listVersions(agentId)])
      .then(([a, v]) => {
        setAgent(a)
        setVersions(v)
        setName(a.name)
        setDescription(a.description)
        setSystemPrompt(a.system_prompt)
        setModel(a.model)
        setAllowedTools(a.allowed_tools)
        setAllowedModels(a.allowed_models)
        setRagSources(a.rag_sources)
        setMaxTokens(a.guardrails.max_tokens)
        setTemperature(a.guardrails.temperature)
        setMaxToolCalls(a.guardrails.max_tool_calls)
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [id, isNew])

  function buildPayload() {
    return {
      name,
      description,
      system_prompt: systemPrompt,
      model,
      allowed_tools: allowedTools,
      allowed_models: allowedModels,
      rag_sources: ragSources,
      guardrails: { ...DEFAULT_GUARDRAILS, max_tokens: maxTokens, temperature, max_tool_calls: maxToolCalls },
    }
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSuccessMsg(null)
    try {
      if (isNew) {
        const created = await createAgent(buildPayload())
        setSuccessMsg('Agent created!')
        navigate(`/agents/${created.id}`)
      } else {
        const updated = await updateAgent(id!, buildPayload())
        setAgent(updated)
        setSuccessMsg('Draft saved.')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  async function handlePublish() {
    if (!id || isNew) return
    setSaving(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const updated = await publishAgent(id)
      setAgent(updated)
      const v = await listVersions(id)
      setVersions(v)
      setSuccessMsg(`Published as version ${updated.version}.`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  async function handleRollback(version: number) {
    if (!id || isNew) return
    setSaving(true)
    setError(null)
    try {
      const updated = await rollbackAgent(id, version)
      setAgent(updated)
      setName(updated.name)
      setDescription(updated.description)
      setSystemPrompt(updated.system_prompt)
      setModel(updated.model)
      setAllowedTools(updated.allowed_tools)
      setAllowedModels(updated.allowed_models)
      setRagSources(updated.rag_sources)
      setMaxTokens(updated.guardrails.max_tokens)
      setTemperature(updated.guardrails.temperature)
      setMaxToolCalls(updated.guardrails.max_tool_calls)
      const v = await listVersions(id)
      setVersions(v)
      setSuccessMsg(`Rolled back to version ${version}.`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  function addTool() {
    const t = newTool.trim()
    if (t && !allowedTools.includes(t)) {
      setAllowedTools([...allowedTools, t])
    }
    setNewTool('')
  }

  function removeTool(tool: string) {
    setAllowedTools(allowedTools.filter((t) => t !== tool))
  }

  function addModel() {
    const m = newModel.trim()
    if (m && !allowedModels.includes(m)) {
      setAllowedModels([...allowedModels, m])
    }
    setNewModel('')
  }

  function removeModel(m: string) {
    setAllowedModels(allowedModels.filter((x) => x !== m))
  }

  function addRagSource() {
    const n = newSourceName.trim()
    if (n && !ragSources.find((s) => s.name === n)) {
      setRagSources([...ragSources, { name: n, top_k: 4, rerank: false }])
    }
    setNewSourceName('')
  }

  function removeRagSource(name: string) {
    setRagSources(ragSources.filter((s) => s.name !== name))
  }

  function updateRagSource(name: string, field: keyof RagSourceRef, value: number | boolean) {
    setRagSources(ragSources.map((s) => (s.name === name ? { ...s, [field]: value } : s)))
  }

  if (loading) return <p className="text-muted-foreground">Loading agent...</p>

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{isNew ? 'New Agent' : `Edit: ${agent?.name ?? ''}`}</h1>
          {agent && (
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={agent.status === 'published' ? 'default' : 'secondary'}>{agent.status}</Badge>
              <span className="text-sm text-muted-foreground">v{agent.version}</span>
            </div>
          )}
        </div>
      </div>

      {error && <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">{error}</div>}
      {successMsg && <div className="rounded-md bg-green-50 border border-green-200 p-3 text-sm text-green-700">{successMsg}</div>}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main form */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Identity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="My Agent" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Input id="description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What does this agent do?" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Behaviour</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="system-prompt">System Prompt</Label>
                <Textarea
                  id="system-prompt"
                  rows={6}
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="You are a helpful assistant."
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="model">Primary Model</Label>
                <Input id="model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="gpt-4o-mini" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Governance — Allowed Tools</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input
                  value={newTool}
                  onChange={(e) => setNewTool(e.target.value)}
                  placeholder="tool_name"
                  onKeyDown={(e) => e.key === 'Enter' && addTool()}
                />
                <Button variant="outline" size="icon" onClick={addTool}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {allowedTools.map((t) => (
                  <Badge key={t} variant="secondary" className="gap-1">
                    {t}
                    <button onClick={() => removeTool(t)} className="hover:text-destructive">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
                {allowedTools.length === 0 && <span className="text-xs text-muted-foreground">No tools allowed (deny-all).</span>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Governance — Allowed Models</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input
                  value={newModel}
                  onChange={(e) => setNewModel(e.target.value)}
                  placeholder="gpt-4o"
                  onKeyDown={(e) => e.key === 'Enter' && addModel()}
                />
                <Button variant="outline" size="icon" onClick={addModel}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {allowedModels.map((m) => (
                  <Badge key={m} variant="secondary" className="gap-1">
                    {m}
                    <button onClick={() => removeModel(m)} className="hover:text-destructive">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
                {allowedModels.length === 0 && <span className="text-xs text-muted-foreground">Empty = primary model only.</span>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>RAG Sources</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input
                  value={newSourceName}
                  onChange={(e) => setNewSourceName(e.target.value)}
                  placeholder="source_name"
                  onKeyDown={(e) => e.key === 'Enter' && addRagSource()}
                />
                <Button variant="outline" size="icon" onClick={addRagSource}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {ragSources.map((src) => (
                <div key={src.name} className="flex items-center gap-3 p-3 rounded-md border">
                  <span className="font-mono text-sm flex-1">{src.name}</span>
                  <div className="flex items-center gap-2 text-sm">
                    <Label className="sr-only">top_k</Label>
                    <span className="text-muted-foreground">top_k</span>
                    <Input
                      type="number"
                      className="w-16 h-8"
                      value={src.top_k}
                      onChange={(e) => updateRagSource(src.name, 'top_k', Number(e.target.value))}
                    />
                    <label className="flex items-center gap-1 text-muted-foreground cursor-pointer">
                      <input
                        type="checkbox"
                        checked={src.rerank}
                        onChange={(e) => updateRagSource(src.name, 'rerank', e.target.checked)}
                      />
                      rerank
                    </label>
                  </div>
                  <button onClick={() => removeRagSource(src.name)} className="text-muted-foreground hover:text-destructive">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
              {ragSources.length === 0 && <span className="text-xs text-muted-foreground">No RAG sources attached.</span>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Guardrails</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="max-tokens">Max Tokens</Label>
                <Input
                  id="max-tokens"
                  type="number"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="temperature">Temperature</Label>
                <Input
                  id="temperature"
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="max-tool-calls">Max Tool Calls</Label>
                <Input
                  id="max-tool-calls"
                  type="number"
                  value={maxToolCalls}
                  onChange={(e) => setMaxToolCalls(Number(e.target.value))}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar: actions + versions */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Actions</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <Button onClick={() => void handleSave()} disabled={saving}>
                {saving ? 'Saving...' : isNew ? 'Create Draft' : 'Save Draft'}
              </Button>
              {!isNew && (
                <Button variant="secondary" onClick={() => void handlePublish()} disabled={saving}>
                  Publish
                </Button>
              )}
              {!isNew && (
                <Button variant="outline" asChild>
                  <Link to={`/agents/${id}/run`}>Run Agent</Link>
                </Button>
              )}
            </CardContent>
          </Card>

          {!isNew && versions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Version History</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {versions.map((v) => (
                  <div key={v.version} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-mono">v{v.version}</span>
                      <Badge variant={v.status === 'published' ? 'default' : 'secondary'} className="text-xs">
                        {v.status}
                      </Badge>
                    </div>
                    <button
                      onClick={() => void handleRollback(v.version)}
                      className="text-muted-foreground hover:text-foreground flex items-center gap-1"
                      title={`Rollback to v${v.version}`}
                    >
                      <RotateCcw className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <Separator />
    </div>
  )
}

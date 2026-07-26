import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { Send, Plus, CheckCircle, XCircle, Bot, Workflow } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import {
  listAgents,
  listConversations,
  getConversation,
  streamChat,
  sendWorkflowChat,
  resumeConversation,
} from '@/lib/api'
import type { AgentManifest, ChatMessage, Conversation, ApprovalRequest } from '@/lib/types'

// ── Constants ─────────────────────────────────────────────────────────────────

const DEMO_WORKFLOW_DEFINITION = {
  steps: [
    { id: 'triage', type: 'agent' as const, agent_id: 'agent-001' },
    { id: 'human_review', type: 'human_approval' as const },
    { id: 'specialist', type: 'agent' as const, agent_id: 'agent-002' },
  ],
  edges: [
    { from: 'triage', to: 'human_review' },
    { from: 'human_review', to: 'specialist' },
  ],
}

// ── Sub-components ────────────────────────────────────────────────────────────

function CitationChip({ source }: { source: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
      {source}
    </span>
  )
}

function ToolCallChip({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[11px] font-mono font-medium text-violet-700">
      {name}()
    </span>
  )
}

function DenialChip({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-[11px] font-mono font-medium text-red-700">
      ⊘ {name}
    </span>
  )
}

function ApprovalCard({
  approval,
  conversationId,
  onResolved,
}: {
  approval: ApprovalRequest
  conversationId: string
  onResolved: (msg: ChatMessage) => void
}) {
  const [loading, setLoading] = useState(false)
  const [resolved, setResolved] = useState(approval.resolved)

  async function handleAction(approved: boolean) {
    setLoading(true)
    try {
      const resp = await resumeConversation(conversationId, {
        run_id: approval.run_id,
        approved,
      })
      setResolved(approved ? 'approved' : 'rejected')
      onResolved(resp.message)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  if (resolved) {
    return (
      <div
        className={cn(
          'mt-2 rounded-lg border px-3 py-2 text-xs font-medium',
          resolved === 'approved'
            ? 'border-green-200 bg-green-50 text-green-700'
            : 'border-red-200 bg-red-50 text-red-700',
        )}
      >
        {resolved === 'approved' ? '✓ Approved' : '✗ Rejected'}
      </div>
    )
  }

  return (
    <div className="mt-2 rounded-lg border border-yellow-200 bg-yellow-50 p-3 space-y-2">
      <p className="text-xs font-medium text-yellow-800">
        Human approval required — step: <span className="font-mono">{approval.pending_step}</span>
      </p>
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={loading}
          className="bg-green-600 hover:bg-green-700 h-7 text-xs"
          onClick={() => void handleAction(true)}
        >
          <CheckCircle className="mr-1 h-3 w-3" />
          Approve
        </Button>
        <Button
          size="sm"
          variant="destructive"
          disabled={loading}
          className="h-7 text-xs"
          onClick={() => void handleAction(false)}
        >
          <XCircle className="mr-1 h-3 w-3" />
          Reject
        </Button>
      </div>
    </div>
  )
}

function MessageBubble({
  message,
  conversationId,
  onApprovalResolved,
}: {
  message: ChatMessage
  conversationId: string
  onApprovalResolved: (msg: ChatMessage) => void
}) {
  const isUser = message.role === 'user'
  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[75%] rounded-2xl px-4 py-2.5 text-sm',
          isUser
            ? 'bg-indigo-600 text-white'
            : 'bg-card border border-border text-card-foreground shadow-sm',
        )}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.citations.map((c, i) => (
              <CitationChip key={i} source={c.source} />
            ))}
          </div>
        )}

        {/* Tool calls */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.tool_calls.map((tc, i) => (
              <ToolCallChip key={i} name={tc.name} />
            ))}
          </div>
        )}

        {/* Governance denials */}
        {message.denied && message.denied.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.denied.map((d) => (
              <DenialChip key={d} name={d} />
            ))}
          </div>
        )}

        {/* Approval card */}
        {message.approval && (
          <ApprovalCard
            approval={message.approval}
            conversationId={conversationId}
            onResolved={onApprovalResolved}
          />
        )}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="max-w-[75%] rounded-2xl border border-border bg-card px-4 py-2.5 text-sm shadow-sm">
        <div className="flex items-center gap-1">
          <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:0ms]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:150ms]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  )
}

// ── ChatPage ──────────────────────────────────────────────────────────────────

type Mode = 'agent' | 'workflow'

export default function ChatPage() {
  const { conversationId: routeConvId } = useParams<{ conversationId: string }>()
  const navigate = useNavigate()

  const [agents, setAgents] = useState<AgentManifest[]>([])
  const [conversations, setConversations] = useState<Omit<Conversation, 'messages'>[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streamingContent, setStreamingContent] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | undefined>(routeConvId)
  const [mode, setMode] = useState<Mode>('agent')
  const [selectedAgentId, setSelectedAgentId] = useState<string>('')
  const [inputValue, setInputValue] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadingConv, setLoadingConv] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Scroll to bottom whenever messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Load agents
  useEffect(() => {
    void listAgents()
      .then((a) => {
        setAgents(a)
        if (a.length > 0 && !selectedAgentId) {
          setSelectedAgentId(a[0].id)
        }
      })
      .catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Load conversation list
  useEffect(() => {
    void listConversations()
      .then(setConversations)
      .catch(() => {})
  }, [conversationId])

  // Load conversation when route changes
  useEffect(() => {
    if (!routeConvId) {
      setMessages([])
      setConversationId(undefined)
      return
    }
    setLoadingConv(true)
    setConversationId(routeConvId)
    void getConversation(routeConvId)
      .then((conv) => {
        setMessages(conv.messages)
        if (conv.agent_id) {
          setMode('agent')
          setSelectedAgentId(conv.agent_id)
        }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoadingConv(false))
  }, [routeConvId])

  function startNewChat() {
    setConversationId(undefined)
    setMessages([])
    setError(null)
    navigate('/chat')
  }

  function handleApprovalResolved(msg: ChatMessage) {
    setMessages((prev) => [...prev, msg])
  }

  async function handleSend() {
    const text = inputValue.trim()
    if (!text || sending) return
    if (mode === 'agent' && !selectedAgentId) {
      setError('Please select an agent.')
      return
    }

    const userMsg: ChatMessage = { role: 'user', content: text, ts: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    setInputValue('')
    setSending(true)
    setError(null)
    setStreamingContent('')

    try {
      if (mode === 'workflow') {
        const resp = await sendWorkflowChat({
          message: text,
          definition: DEMO_WORKFLOW_DEFINITION,
          conversation_id: conversationId,
        })
        setConversationId(resp.conversation_id)
        if (!conversationId) {
          navigate(`/chat/${resp.conversation_id}`, { replace: true })
        }
        setMessages((prev) => [...prev, resp.message])
        setStreamingContent(null)
        void listConversations().then(setConversations).catch(() => {})
      } else {
        await streamChat(
          selectedAgentId,
          { message: text, conversation_id: conversationId },
          (token) => {
            setStreamingContent((prev) => (prev ?? '') + token)
          },
          (finalMsg) => {
            setStreamingContent(null)
            setMessages((prev) => [...prev, finalMsg])
            void listConversations().then(setConversations).catch(() => {})
          },
        )
        // After streamChat resolves, update conversation id
        // Note: streamChat calls onDone with the full message; conversation_id
        // is managed by mock internally. We re-fetch conversations to pick up
        // the new one.
      }
    } catch (e: unknown) {
      setStreamingContent(null)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      void handleSend()
    }
  }

  const currentConvId = conversationId ?? 'new'

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-0 -mx-6 -my-8 lg:-mx-10">
      {/* Left rail: conversation list */}
      <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-sidebar">
        <div className="flex items-center justify-between border-b border-sidebar-border px-4 py-3">
          <span className="text-sm font-semibold text-sidebar-foreground">Conversations</span>
          <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={startNewChat} title="New chat">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto py-1">
          {conversations.length === 0 && (
            <p className="px-4 py-3 text-xs text-sidebar-muted">No conversations yet.</p>
          )}
          {conversations.map((conv) => (
            <Link
              key={conv.id}
              to={`/chat/${conv.id}`}
              className={cn(
                'block px-4 py-2.5 text-sm transition-colors hover:bg-white/5',
                routeConvId === conv.id ? 'bg-white/10 text-sidebar-foreground' : 'text-sidebar-muted',
              )}
            >
              <div className="truncate font-medium">{conv.title}</div>
              <div className="mt-0.5 text-[11px] text-sidebar-muted/70">
                {new Date(conv.created_at).toLocaleDateString()}
                {conv.agent_id && (
                  <span className="ml-1 text-sidebar-muted/50">· {conv.agent_id}</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      </aside>

      {/* Main chat area */}
      <div className="flex flex-1 flex-col overflow-hidden bg-background">
        {/* Header / mode selector */}
        <div className="flex items-center gap-3 border-b border-border px-6 py-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setMode('agent')}
              className={cn(
                'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                mode === 'agent'
                  ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Bot className="h-4 w-4" />
              Agent
            </button>
            <button
              onClick={() => setMode('workflow')}
              className={cn(
                'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                mode === 'workflow'
                  ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Workflow className="h-4 w-4" />
              Workflow
            </button>
          </div>

          {mode === 'agent' && agents.length > 0 && (
            <select
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              className="rounded-lg border border-border bg-background px-2 py-1.5 text-sm text-foreground outline-none focus:border-indigo-500"
            >
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          )}

          {mode === 'workflow' && (
            <Badge variant="secondary" className="text-xs">
              Triage → Human review → Specialist
            </Badge>
          )}
        </div>

        {/* Error banner */}
        {error && (
          <div className="mx-6 mt-3 rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loadingConv && (
            <p className="text-center text-sm text-muted-foreground">Loading conversation...</p>
          )}

          {!loadingConv && messages.length === 0 && !streamingContent && (
            <Card className="mx-auto mt-16 max-w-sm border-dashed">
              <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
                {mode === 'agent' ? (
                  <Bot className="h-8 w-8 opacity-40" />
                ) : (
                  <Workflow className="h-8 w-8 opacity-40" />
                )}
                <p className="text-sm font-medium">Start a conversation</p>
                <p className="text-xs">
                  {mode === 'agent'
                    ? 'Ask the agent anything. Replies may include citations, tool calls, and governance notices.'
                    : 'Send a message to trigger the Triage → Human review → Specialist workflow.'}
                </p>
              </CardContent>
            </Card>
          )}

          <div className="space-y-3">
            {messages.map((msg, i) => (
              <MessageBubble
                key={i}
                message={msg}
                conversationId={currentConvId}
                onApprovalResolved={handleApprovalResolved}
              />
            ))}

            {/* Streaming bubble */}
            {streamingContent !== null && (
              <div className="flex justify-start">
                <div className="max-w-[75%] rounded-2xl border border-border bg-card px-4 py-2.5 text-sm shadow-sm">
                  <p className="whitespace-pre-wrap leading-relaxed">{streamingContent || ' '}</p>
                </div>
              </div>
            )}

            {/* Typing indicator (before first token arrives) */}
            {sending && streamingContent === '' && <TypingIndicator />}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-border px-6 py-3">
          <div className="flex gap-2 items-end">
            <Textarea
              rows={2}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                mode === 'agent'
                  ? 'Message the agent… (⌘↵ to send)'
                  : 'Trigger the workflow… (⌘↵ to send)'
              }
              className="resize-none"
              disabled={sending}
            />
            <Button
              onClick={() => void handleSend()}
              disabled={sending || !inputValue.trim()}
              className="shrink-0"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

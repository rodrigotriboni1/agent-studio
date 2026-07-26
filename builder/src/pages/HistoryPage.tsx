import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { MessageSquare, ArrowRight, Clock } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { listConversations, getConversation } from '@/lib/api'
import type { Conversation, ChatMessage } from '@/lib/types'

function MessageRow({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[75%] rounded-xl px-3 py-2 text-sm',
          isUser ? 'bg-indigo-600 text-white' : 'bg-muted text-foreground',
        )}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {message.citations && message.citations.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {message.citations.map((c, i) => (
              <span
                key={i}
                className="rounded-full border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-700"
              >
                {c.source}
              </span>
            ))}
          </div>
        )}
        {message.denied && message.denied.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {message.denied.map((d) => (
              <span
                key={d}
                className="rounded-full border border-red-200 bg-red-50 px-1.5 py-0.5 text-[10px] text-red-700"
              >
                ⊘ {d}
              </span>
            ))}
          </div>
        )}
        <div className="mt-1 text-[10px] opacity-60">
          {new Date(message.ts).toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}

function ConversationDetail({ conversationId }: { conversationId: string }) {
  const [conv, setConv] = useState<Conversation | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getConversation(conversationId)
      .then(setConv)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [conversationId])

  if (loading) return <p className="text-muted-foreground text-sm">Loading conversation...</p>
  if (error) return (
    <div className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
      {error}
    </div>
  )
  if (!conv) return null

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-lg">{conv.title}</CardTitle>
        <Button size="sm" asChild>
          <Link to={`/chat/${conv.id}`}>
            <MessageSquare className="mr-1.5 h-4 w-4" />
            Continue in chat
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {conv.messages.map((msg, i) => (
            <MessageRow key={i} message={msg} />
          ))}
          {conv.messages.length === 0 && (
            <p className="text-sm text-muted-foreground">No messages in this conversation.</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default function HistoryPage() {
  const { conversationId } = useParams<{ conversationId: string }>()
  const [conversations, setConversations] = useState<Omit<Conversation, 'messages'>[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listConversations()
      .then(setConversations)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <PageHeader
        title="History"
        description="Browse past conversations and workflow runs."
        actions={
          <Button asChild>
            <Link to="/chat">
              <MessageSquare className="mr-2 h-4 w-4" />
              New Chat
            </Link>
          </Button>
        }
      />

      {error && (
        <div className="mb-4 rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Conversation list */}
        <div className="space-y-2">
          {loading && <p className="text-sm text-muted-foreground">Loading conversations...</p>}
          {!loading && conversations.length === 0 && (
            <Card>
              <CardContent className="flex flex-col items-center py-8 text-center text-muted-foreground">
                <Clock className="mb-2 h-6 w-6 opacity-40" />
                <p className="text-sm">No conversations yet.</p>
                <Button asChild size="sm" className="mt-3">
                  <Link to="/chat">Start chatting</Link>
                </Button>
              </CardContent>
            </Card>
          )}
          {conversations.map((conv) => (
            <Link key={conv.id} to={`/history/${conv.id}`}>
              <Card
                className={cn(
                  'cursor-pointer transition-shadow hover:shadow-md',
                  conversationId === conv.id && 'ring-2 ring-indigo-500',
                )}
              >
                <CardContent className="flex items-start justify-between gap-2 p-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="truncate text-sm font-medium">{conv.title}</span>
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {new Date(conv.created_at).toLocaleDateString(undefined, {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })}
                      {conv.agent_id && (
                        <Badge variant="secondary" className="text-[10px]">
                          {conv.agent_id}
                        </Badge>
                      )}
                    </div>
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        {/* Conversation detail */}
        <div className="lg:col-span-2">
          {conversationId ? (
            <ConversationDetail conversationId={conversationId} />
          ) : (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center py-16 text-center text-muted-foreground">
                <MessageSquare className="mb-2 h-8 w-8 opacity-30" />
                <p className="text-sm">Select a conversation to view its messages.</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

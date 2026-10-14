import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  GraduationCap,
  LogOut,
  MessageSquarePlus,
  Trash2,
  BookOpen,
  AlertCircle,
  Menu,
  X,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { conversationsApi } from '../api/conversations'
import { ApiError } from '../api/client'
import ChatMessage from '../components/chat/ChatMessage'
import ChatInput from '../components/chat/ChatInput'
import SuggestedQuestions from '../components/chat/SuggestedQuestions'
import Button from '../components/ui/Button'
import type { Conversation, ConversationDetail, Message } from '../types'
import clsx from 'clsx'

export default function StudentDashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { conversationId } = useParams()

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [active, setActive] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [sendingMsg, setSendingMsg] = useState(false)
  const [error, setError] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Load conversation list
  const refreshList = useCallback(async () => {
    try {
      const res = await conversationsApi.list()
      setConversations(res.items)
    } catch {
      // silent
    }
  }, [])

  useEffect(() => {
    void refreshList()
  }, [refreshList])

  // Load active conversation
  useEffect(() => {
    if (!conversationId) {
      setActive(null)
      return
    }
    setLoading(true)
    setError('')
    conversationsApi
      .get(conversationId)
      .then(setActive)
      .catch((err: ApiError) => {
        setError(err.detail)
        setActive(null)
      })
      .finally(() => setLoading(false))
  }, [conversationId])

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [active?.messages])

  async function handleNewChat() {
    try {
      const conv = await conversationsApi.create()
      await refreshList()
      navigate(`/chat/${conv.id}`)
      setSidebarOpen(false)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Could not create conversation')
    }
  }

  async function handleSend(question: string) {
    if (!active) {
      // Create new conversation first
      setSendingMsg(true)
      try {
        const conv = await conversationsApi.create()
        await conversationsApi.ask(conv.id, question)
        await refreshList()
        navigate(`/chat/${conv.id}`)
        // Load full detail
        const detail = await conversationsApi.get(conv.id)
        setActive(detail)
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : 'Failed to send message')
      } finally {
        setSendingMsg(false)
      }
      return
    }

    // Optimistic user message
    const optimisticMsg: Message = {
      id: `opt-${Date.now()}`,
      role: 'user',
      content: question,
      insufficient_evidence: false,
      created_at: new Date().toISOString(),
      citations: [],
    }
    setActive(prev =>
      prev ? { ...prev, messages: [...prev.messages, optimisticMsg] } : prev
    )
    setSendingMsg(true)
    setError('')

    try {
      await conversationsApi.ask(active.id, question)
      const updated = await conversationsApi.get(active.id)
      setActive(updated)
      await refreshList()
    } catch (err) {
      setActive(prev =>
        prev
          ? {
              ...prev,
              messages: prev.messages.filter(m => m.id !== optimisticMsg.id),
            }
          : prev
      )
      setError(err instanceof ApiError ? err.detail : 'Failed to get answer')
    } finally {
      setSendingMsg(false)
    }
  }

  async function handleDeleteConv(id: string) {
    await conversationsApi.delete(id)
    setConversations(cs => cs.filter(c => c.id !== id))
    if (conversationId === id) {
      navigate('/chat')
      setActive(null)
    }
  }

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* ── Mobile sidebar overlay ── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        className={clsx(
          'fixed md:static inset-y-0 left-0 z-30 w-72 bg-white border-r border-gray-100 flex flex-col transition-transform duration-200',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        )}
      >
        {/* Brand */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
          <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center shrink-0">
            <GraduationCap className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-gray-900 text-sm leading-tight">CampusPolicy AI</p>
            <p className="text-xs text-gray-400 truncate">{user?.email}</p>
          </div>
          <button
            className="md:hidden p-1 rounded text-gray-400 hover:text-gray-600"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* New chat */}
        <div className="p-3 border-b border-gray-100">
          <Button
            variant="primary"
            className="w-full gap-2"
            onClick={handleNewChat}
          >
            <MessageSquarePlus className="w-4 h-4" />
            New conversation
          </Button>
        </div>

        {/* Conversation list */}
        <nav className="flex-1 overflow-y-auto scrollbar-thin py-2" aria-label="Conversations">
          {conversations.length === 0 ? (
            <p className="px-4 py-6 text-xs text-gray-400 text-center">
              No conversations yet. Start by asking a question!
            </p>
          ) : (
            conversations.map(conv => (
              <div
                key={conv.id}
                className={clsx(
                  'group flex items-center gap-2 px-3 py-2.5 mx-2 rounded-lg cursor-pointer transition-colors',
                  conv.id === conversationId
                    ? 'bg-brand-50 text-brand-700'
                    : 'hover:bg-gray-50 text-gray-700'
                )}
                onClick={() => {
                  navigate(`/chat/${conv.id}`)
                  setSidebarOpen(false)
                }}
                role="button"
                tabIndex={0}
                onKeyDown={e => e.key === 'Enter' && navigate(`/chat/${conv.id}`)}
                aria-current={conv.id === conversationId ? 'page' : undefined}
              >
                <BookOpen className="w-3.5 h-3.5 shrink-0 opacity-60" />
                <span className="flex-1 text-xs truncate">
                  {conv.title ?? 'New conversation'}
                </span>
                <button
                  onClick={e => {
                    e.stopPropagation()
                    void handleDeleteConv(conv.id)
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 hover:text-red-500 transition-all"
                  aria-label={`Delete conversation: ${conv.title ?? 'untitled'}`}
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))
          )}
        </nav>

        {/* Logout */}
        <div className="p-3 border-t border-gray-100">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Main chat area ── */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-100 px-4 py-3 flex items-center gap-3">
          <button
            className="md:hidden p-1.5 rounded-lg text-gray-500 hover:bg-gray-100"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h1 className="text-sm font-semibold text-gray-800 truncate">
            {active?.title ?? 'Ask about college policies'}
          </h1>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-6">
          {loading ? (
            <div className="flex justify-center pt-12">
              <div className="w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : !active || active.messages.length === 0 ? (
            <EmptyState onSelect={handleSend} />
          ) : (
            <div className="max-w-3xl mx-auto space-y-6">
              {active.messages.map(msg => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              {sendingMsg && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                    <GraduationCap className="w-4 h-4 text-gray-600" />
                  </div>
                  <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                    <ThinkingDots />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Error banner */}
        {error && (
          <div
            role="alert"
            className="mx-4 mb-2 flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
            <button
              onClick={() => setError('')}
              className="ml-auto text-red-400 hover:text-red-600"
              aria-label="Dismiss error"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Input */}
        <div className="bg-white border-t border-gray-100 px-4 py-3">
          <div className="max-w-3xl mx-auto">
            <ChatInput onSend={handleSend} disabled={sendingMsg} />
            <p className="text-center text-xs text-gray-400 mt-2">
              Answers are grounded in uploaded college documents. Always verify with your institution.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}

function EmptyState({ onSelect }: { onSelect: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[60vh] gap-6 px-4">
      <div className="w-16 h-16 bg-brand-100 rounded-2xl flex items-center justify-center">
        <GraduationCap className="w-8 h-8 text-brand-600" />
      </div>
      <div className="text-center max-w-sm">
        <h2 className="text-xl font-semibold text-gray-800 mb-2">
          Ask about college policies
        </h2>
        <p className="text-sm text-gray-500">
          Get instant answers from official documents — attendance rules, exam procedures,
          student handbook, and more.
        </p>
      </div>
      <SuggestedQuestions onSelect={onSelect} />
    </div>
  )
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 py-1" aria-label="Assistant is thinking">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
          style={{ animationDelay: `${i * 150}ms` }}
        />
      ))}
    </div>
  )
}

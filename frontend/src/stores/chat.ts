import { create } from 'zustand'
import { chatApi } from '@/api/chat'
import type { ChatInterruptPayload, ChatMessage, ChatSession } from '@/api/types'

interface ChatStore {
  sessions: ChatSession[]
  currentSessionId: string | null
  currentThreadId: string | null
  messages: ChatMessage[]
  pendingAction: ChatInterruptPayload | null
  loading: boolean
  sending: boolean

  fetchSessions: () => Promise<void>
  createSession: () => Promise<void>
  selectSession: (id: string) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  sendMessage: (text: string) => Promise<void>
  resumeAction: (confirmed: boolean) => Promise<void>
  clearMessages: () => void
}

function threadIdForSession(sessionId: string): string {
  return `email-${sessionId}`
}

export const useChatStore = create<ChatStore>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  currentThreadId: null,
  messages: [],
  pendingAction: null,
  loading: false,
  sending: false,

  fetchSessions: async () => {
    set({ loading: true })
    try {
      const sessions = await chatApi.getSessions()
      set({ sessions })
    } finally {
      set({ loading: false })
    }
  },

  createSession: async () => {
    try {
      const session = await chatApi.createSession()
      set((state) => ({ sessions: [session, ...state.sessions] }))
      set({
        currentSessionId: session.id,
        currentThreadId: threadIdForSession(session.id),
        messages: [],
        pendingAction: null,
      })
    } catch {
      throw new Error('创建会话失败')
    }
  },

  selectSession: async (id: string) => {
    set({
      currentSessionId: id,
      currentThreadId: threadIdForSession(id),
      messages: [],
      pendingAction: null,
    })
    try {
      const res = await chatApi.getSession(id)
      set({
        currentThreadId: res.thread_id ?? threadIdForSession(id),
        messages: res.messages,
        pendingAction: res.status === 'interrupted' ? (res.interrupt ?? null) : null,
      })
    } catch {
      set({
        currentSessionId: null,
        currentThreadId: null,
        messages: [],
        pendingAction: null,
      })
    }
  },

  deleteSession: async (id: string) => {
    await chatApi.deleteSession(id)
    set((state) => {
      const isCurrent = state.currentSessionId === id
      return {
        sessions: state.sessions.filter((session) => session.id !== id),
        currentSessionId: isCurrent ? null : state.currentSessionId,
        currentThreadId: isCurrent ? null : state.currentThreadId,
        messages: isCurrent ? [] : state.messages,
        pendingAction: isCurrent ? null : state.pendingAction,
      }
    })
    try {
      await get().fetchSessions()
    } catch {
      // Keep the optimistic removal even if the reconciliation request fails.
    }
  },

  sendMessage: async (text: string) => {
    const { currentSessionId } = get()
    set({ sending: true })
    try {
      const res = await chatApi.sendMessage(currentSessionId, text)
      set({
        currentSessionId: res.session_id,
        currentThreadId: res.thread_id ?? threadIdForSession(res.session_id),
        messages: res.messages,
        pendingAction: res.status === 'interrupted' ? (res.interrupt ?? null) : null,
      })
      if (res.status === 'completed') {
        await get().fetchSessions()
      }
    } finally {
      set({ sending: false })
    }
  },

  resumeAction: async (confirmed: boolean) => {
    const { currentThreadId } = get()
    if (!currentThreadId) {
      throw new Error('当前没有可恢复的会话')
    }

    set({ sending: true })
    try {
      const res = await chatApi.resumeAction(currentThreadId, confirmed)
      set({
        currentSessionId: res.session_id,
        currentThreadId: res.thread_id ?? currentThreadId,
        messages: res.messages,
        pendingAction: res.status === 'interrupted' ? (res.interrupt ?? null) : null,
      })
      await get().fetchSessions()
    } finally {
      set({ sending: false })
    }
  },

  clearMessages: () => set({ messages: [], pendingAction: null }),
}))

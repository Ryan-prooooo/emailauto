import api, { unwrap } from './index'
import type { ChatResponse, ChatSession } from './types'

export const chatApi = {
  sendMessage(
    sessionId: string | null,
    message: string,
  ): Promise<ChatResponse> {
    return unwrap<ChatResponse>(api.post('/chat', {
      session_id: sessionId,
      message,
    }))
  },

  getSessions(): Promise<ChatSession[]> {
    return unwrap<ChatSession[]>(api.get('/chat/sessions'))
  },

  getSession(sessionId: string): Promise<ChatResponse> {
    return unwrap<ChatResponse>(api.get(`/chat/${sessionId}`))
  },

  deleteSession(sessionId: string): Promise<{ success: boolean }> {
    return unwrap<{ success: boolean }>(api.delete(`/chat/${sessionId}`))
  },

  createSession(): Promise<ChatSession> {
    return unwrap<ChatSession>(api.post('/chat/sessions', {}))
  },

  resumeAction(
    threadId: string,
    confirmed: boolean,
  ): Promise<ChatResponse> {
    return unwrap<ChatResponse>(api.post('/chat/resume', {
      thread_id: threadId,
      confirmed,
    }))
  },
}

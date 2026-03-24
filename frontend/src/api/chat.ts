import { request } from '@/api/index'
import type { ChatResponse, ChatSession, IntentMode } from '@/api/types'

export const chatApi = {
  // 发送消息
  sendMessage(sessionId: number | null, message: string, forceIntent: IntentMode = 'auto'): Promise<ChatResponse> {
    return request.post('/chat', {
      session_id: sessionId,
      message,
      force_intent: forceIntent === 'auto' ? null : forceIntent,
    })
  },

  // 获取会话列表
  getSessions(): Promise<ChatSession[]> {
    return request.get('/chat/sessions')
  },

  // 获取会话消息
  getSession(sessionId: number): Promise<ChatResponse> {
    return request.get(`/chat/${sessionId}`)
  },

  // 删除会话
  deleteSession(sessionId: number): Promise<{ success: boolean }> {
    return request.delete(`/chat/${sessionId}`)
  },

  // 创建新会话
  createSession(): Promise<ChatSession> {
    return request.post('/chat/sessions', {})
  }
}

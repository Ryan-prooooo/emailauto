import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockChatApi } = vi.hoisted(() => ({
  mockChatApi: {
    getSessions: vi.fn(),
    createSession: vi.fn(),
    getSession: vi.fn(),
    deleteSession: vi.fn(),
    sendMessage: vi.fn(),
    resumeAction: vi.fn(),
  },
}))

vi.mock('@/api/chat', () => ({
  chatApi: mockChatApi,
}))

import { useChatStore } from './chat'

describe('useChatStore.deleteSession', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useChatStore.setState({
      sessions: [
        { id: 'session-1', title: 'First', updated_at: '2026-04-28T13:00:00' },
        { id: 'session-2', title: 'Second', updated_at: '2026-04-28T13:01:00' },
      ],
      currentSessionId: 'session-1',
      currentThreadId: 'email-session-1',
      messages: [{ role: 'user', content: 'hello', created_at: '2026-04-28T13:00:00' }],
      pendingAction: { type: 'confirmation', title: 'Confirm', message: 'Pending' },
      loading: false,
      sending: false,
    })
  })

  it('optimistically removes the deleted current session before refreshing', async () => {
    mockChatApi.deleteSession.mockResolvedValue({ success: true })
    mockChatApi.getSessions.mockRejectedValue(new Error('refresh failed'))

    await useChatStore.getState().deleteSession('session-1')

    const state = useChatStore.getState()
    expect(mockChatApi.deleteSession).toHaveBeenCalledWith('session-1')
    expect(state.sessions).toEqual([
      { id: 'session-2', title: 'Second', updated_at: '2026-04-28T13:01:00' },
    ])
    expect(state.currentSessionId).toBeNull()
    expect(state.currentThreadId).toBeNull()
    expect(state.messages).toEqual([])
    expect(state.pendingAction).toBeNull()
  })
})

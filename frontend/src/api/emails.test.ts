import { describe, expect, it, vi, beforeEach } from 'vitest'

const { getMock, postMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
}))

vi.mock('./index', () => ({
  default: {
    get: getMock,
    post: postMock,
  },
  unwrap: <T>(promise: Promise<T>) => promise,
}))

import { emailApi } from './emails'

describe('emailApi', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
  })

  it('returns the email list when the shared api client already unwraps response.data', async () => {
    getMock.mockResolvedValue([
      {
        id: 'email-1',
        message_id: 'msg-1',
        subject: 'hello',
        sender: 'alice@example.com',
        category: null,
        is_processed: true,
      },
    ])

    await expect(emailApi.getAll()).resolves.toEqual([
      expect.objectContaining({
        id: 'email-1',
        subject: 'hello',
        sender: 'alice@example.com',
        processed: true,
      }),
    ])
  })

  it('normalizes backend email fields for the dashboard and timeline pages', async () => {
    getMock.mockResolvedValue([
      {
        id: 'email-1',
        message_id: 'msg-1',
        subject: 'hello',
        sender: 'alice@example.com',
        recipient: 'bob@example.com',
        date: '2026-04-27T12:00:00Z',
        body_text: 'plain body',
        body_html: '<p>plain body</p>',
        category: 'work',
        is_read: true,
        is_processed: false,
      },
    ])

    await expect(emailApi.getAll()).resolves.toEqual([
      {
        id: 'email-1',
        message_id: 'msg-1',
        subject: 'hello',
        sender: 'alice@example.com',
        sender_email: 'alice@example.com',
        recipient: 'bob@example.com',
        received_at: '2026-04-27T12:00:00Z',
        category: 'work',
        summary: null,
        processed: false,
        content_text: 'plain body',
        content_html: '<p>plain body</p>',
        is_read: true,
      },
    ])
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getMock, deleteMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  deleteMock: vi.fn(),
}))

vi.mock('./index', () => ({
  default: {
    get: getMock,
    delete: deleteMock,
  },
  unwrap: <T>(promise: Promise<T>) => promise,
}))

import { eventApi } from './events'

describe('eventApi', () => {
  beforeEach(() => {
    getMock.mockReset()
    deleteMock.mockReset()
  })

  it('normalizes backend event fields for dashboard and timeline pages', async () => {
    getMock.mockResolvedValue([
      {
        id: 'event-1',
        email_id: 'email-1',
        event_type: 'meeting',
        title: 'Team sync',
        description: 'Weekly sync',
        start_time: '2026-04-27T09:00:00Z',
        end_time: '2026-04-27T10:00:00Z',
        location: 'Meeting room',
        status: 'important',
        organizer: 'alice@example.com',
        attendees: 'bob@example.com',
        rsvp_status: 'pending',
        meeting_link: 'https://example.com/meet',
        email_subject: 'Weekly sync',
        email_sender: 'alice@example.com',
      },
    ])

    await expect(eventApi.getAll()).resolves.toEqual([
      {
        id: 'event-1',
        email_id: 'email-1',
        event_type: 'meeting',
        title: 'Team sync',
        description: 'Weekly sync',
        event_time: '2026-04-27T09:00:00Z',
        start_time: '2026-04-27T09:00:00Z',
        end_time: '2026-04-27T10:00:00Z',
        location: 'Meeting room',
        important: true,
        actionable: true,
        action_items: null,
        processed: false,
        status: 'important',
        organizer: 'alice@example.com',
        attendees: 'bob@example.com',
        rsvp_status: 'pending',
        meeting_link: 'https://example.com/meet',
        email_subject: 'Weekly sync',
        email_sender: 'alice@example.com',
      },
    ])
  })
})

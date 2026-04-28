import api, { unwrap } from './index'
import type { Event } from './types'

interface BackendEvent {
  id: string
  email_id: string | null
  event_type: string | null
  title: string
  description: string | null
  start_time?: string | null
  end_time?: string | null
  location: string | null
  status: string
  organizer?: string | null
  attendees?: string | null
  rsvp_status?: string | null
  meeting_link?: string | null
  email_subject?: string | null
  email_sender?: string | null
}

function normalizeEvent(event: BackendEvent): Event {
  const actionable = event.rsvp_status === 'pending' || event.status === 'pending'
  return {
    id: event.id,
    email_id: event.email_id,
    event_type: event.event_type ?? '',
    title: event.title,
    description: event.description,
    event_time: event.start_time ?? null,
    start_time: event.start_time ?? null,
    end_time: event.end_time ?? null,
    location: event.location,
    important: event.status === 'important',
    actionable,
    action_items: null,
    processed: !actionable,
    status: event.status,
    organizer: event.organizer ?? null,
    attendees: event.attendees ?? null,
    rsvp_status: event.rsvp_status ?? null,
    meeting_link: event.meeting_link ?? null,
    email_subject: event.email_subject ?? null,
    email_sender: event.email_sender ?? null,
  }
}

export const eventApi = {
  getAll(params?: { skip?: number; limit?: number; event_type?: string; important?: boolean }) {
    return unwrap<BackendEvent[]>(api.get<BackendEvent[]>('/events', { params })).then((events) =>
      events.map(normalizeEvent),
    )
  },

  getById(id: string) {
    return unwrap<BackendEvent>(api.get<BackendEvent>(`/events/${id}`)).then(normalizeEvent)
  },

  delete(id: string) {
    return api.delete(`/events/${id}`)
  },
}

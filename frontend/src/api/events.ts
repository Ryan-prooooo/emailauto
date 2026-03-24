import api from './index'
import type { Event } from './types'

export const eventApi = {
  getAll(params?: { limit?: number; event_type?: string }) {
    return api.get<Event[]>('/events', { params })
  },

  getById(id: number) {
    return api.get<Event>(`/events/${id}`)
  },

  delete(id: number) {
    return api.delete(`/events/${id}`)
  }
}

import { create } from 'zustand'
import { eventApi } from '@/api/events'
import type { Event } from '@/api/types'

interface EventStore {
  events: Event[]
  loading: boolean
  fetchEvents: (params?: { skip?: number; limit?: number; event_type?: string; important?: boolean }) => Promise<void>
  deleteEvent: (id: string) => Promise<void>
}

export const useEventStore = create<EventStore>((set) => ({
  events: [],
  loading: false,

  fetchEvents: async (params) => {
    set({ loading: true })
    try {
      const events = await eventApi.getAll(params)
      set({ events })
    } finally {
      set({ loading: false })
    }
  },

  deleteEvent: async (id: string) => {
    await eventApi.delete(id)
    set((s) => ({ events: s.events.filter((e) => e.id !== id) }))
  },
}))

export function filterImportant(events: Event[]) {
  return events.filter((e) => e.important)
}

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { eventApi } from '@/api/events'
import type { Event } from '@/api/types'

export const useEventStore = defineStore('event', () => {
  const events = ref<Event[]>([])
  const loading = ref(false)

  const importantEvents = computed(() => events.value.filter(e => e.important))
  const pendingEvents = computed(() => events.value.filter(e => e.actionable))

  async function fetchEvents(params?: { limit?: number; event_type?: string }) {
    loading.value = true
    try {
      events.value = await eventApi.getAll(params)
    } finally {
      loading.value = false
    }
  }

  async function deleteEvent(id: number) {
    await eventApi.delete(id)
    events.value = events.value.filter(e => e.id !== id)
  }

  return { events, loading, importantEvents, pendingEvents, fetchEvents, deleteEvent }
})

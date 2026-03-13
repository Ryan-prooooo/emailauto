import api from './index'
import type { Email } from './types'

export const emailApi = {
  getAll(params?: { limit?: number; category?: string; processed?: boolean }) {
    return api.get<Email[]>('/emails', { params })
  },

  getById(id: number) {
    return api.get<Email>(`/emails/${id}`)
  },

  sync(data?: { days?: number; limit?: number }) {
    return api.post('/emails/sync', data)
  },

  parseAll() {
    return api.post('/emails/parse-all')
  },

  parseOne(id: number) {
    return api.post(`/emails/${id}/parse`)
  }
}

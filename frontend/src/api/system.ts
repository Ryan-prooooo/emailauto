import api from './index'
import type { Settings } from './types'

export const systemApi = {
  getSettings() {
    return api.get<Settings>('/settings')
  },

  updateSettings(data: Partial<Settings>) {
    return api.put('/settings', data)
  },

  testConnection() {
    return api.post('/settings/test-connection')
  },

  getJobs() {
    return api.get('/scheduler/jobs')
  },

  triggerSync() {
    return api.post('/scheduler/trigger-sync')
  },

  triggerParse() {
    return api.post('/scheduler/trigger-parse')
  },

  sendDailySummary(toEmail?: string) {
    return api.post('/mailer/send-daily-summary', null, { params: { to_email: toEmail } })
  },

  getLogs(params?: { limit?: number }) {
    return api.get('/system/logs', { params })
  }
}

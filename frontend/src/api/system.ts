import api, { unwrap } from './index'
import type { Settings, Job } from './types'

export interface TestConnectionResponse {
  success: boolean
  message: string
}

export interface UpdateSettingsResponse {
  success: boolean
  message: string
}

export interface TriggerSyncResponse {
  success: boolean
  synced: number
  errors: string[]
}

export interface TriggerParseResponse {
  processed: number
  failed: number
}

export interface SendDailySummaryResponse {
  success: boolean
}

export const systemApi = {
  getSettings(): Promise<Settings> {
    return unwrap<Settings>(api.get<Settings>('/settings'))
  },

  updateSettings(data: Partial<Settings>): Promise<UpdateSettingsResponse> {
    return unwrap<UpdateSettingsResponse>(api.put('/settings', data))
  },

  testConnection(): Promise<TestConnectionResponse> {
    return unwrap<TestConnectionResponse>(api.post('/settings/test-connection'))
  },

  getJobs(): Promise<Job[]> {
    return unwrap<Job[]>(api.get<Job[]>('/scheduler/jobs'))
  },

  triggerSync(): Promise<TriggerSyncResponse> {
    return unwrap<TriggerSyncResponse>(api.post<TriggerSyncResponse>('/scheduler/trigger-sync'))
  },

  triggerParse(): Promise<TriggerParseResponse> {
    return unwrap<TriggerParseResponse>(api.post<TriggerParseResponse>('/scheduler/trigger-parse'))
  },

  sendDailySummary(toEmail?: string): Promise<SendDailySummaryResponse> {
    return unwrap<SendDailySummaryResponse>(
      api.post<SendDailySummaryResponse>('/mailer/send-daily-summary', null, { params: { to_email: toEmail } }),
    )
  },
}

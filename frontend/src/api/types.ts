export interface Email {
  id: string
  message_id: string
  subject: string
  sender: string
  sender_email: string
  recipient?: string
  received_at: string
  category: string | null
  summary: string | null
  processed: boolean
  content_text?: string
  content_html?: string
  is_read?: boolean
}

export interface Event {
  id: string
  email_id: string | null
  event_type: string
  title: string
  description: string | null
  event_time: string | null
  start_time?: string | null
  end_time?: string | null
  location: string | null
  important: boolean
  actionable: boolean
  action_items: string | null
  processed: boolean
  status?: string
  organizer?: string | null
  attendees?: string | null
  rsvp_status?: string | null
  meeting_link?: string | null
  email_subject?: string | null
  email_sender?: string | null
}

export interface Reminder {
  id: string
  title: string
  remind_at: string
  sent: boolean
  event_id?: string
}

export interface Settings {
  categories: string[]
  check_interval: number
  scheduled_send_hour: number
  scheduled_send_minute: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatSession {
  id: string
  title: string
  updated_at: string
}

export interface ChatInterruptPayload {
  type: string
  title: string
  message: string
  draft_content?: string
  sender_email?: string
  email_id?: string | number
  event_id?: string | number
  [key: string]: unknown
}

export interface ChatResponse {
  session_id: string
  messages: ChatMessage[]
  status: 'completed' | 'interrupted'
  thread_id?: string | null
  interrupt?: ChatInterruptPayload | null
}

export interface SyncResponse {
  success: boolean
  synced: number
  errors: string[]
}

export interface ParseAllResponse {
  processed: number
}

export interface Job {
  id: string
  name: string
  next_run_time: string | null
}

export type IntentMode = 'auto' | 'react'  // TODO: 后续按需支持手动指定 intent 类型

export interface Email {
  id: number
  message_id?: string
  subject: string
  sender: string
  sender_email?: string
  recipient?: string
  received_at: string
  category: string | null
  summary?: string | null
  processed: boolean
  content_text?: string
  content_html?: string
  is_read?: boolean
}

export interface Event {
  id: number
  title: string
  event_type: string
  description?: string | null
  event_time: string | null
  location?: string | null
  important: boolean
  actionable: boolean
  action_items?: string | null
  email_id: number
  details?: Record<string, any>
}

export interface Reminder {
  id: number
  title: string
  remind_at: string
  sent: boolean
  event_id?: number
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
  id: number
  title: string
  updated_at: string
}

export interface ChatResponse {
  session_id: number
  messages: ChatMessage[]
}

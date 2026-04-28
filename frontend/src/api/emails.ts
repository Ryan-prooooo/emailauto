import api, { unwrap } from './index'
import type { Email, SyncResponse, ParseAllResponse } from './types'

interface BackendEmail {
  id: string
  message_id: string
  subject: string | null
  sender: string | null
  recipient?: string | null
  date?: string | null
  body_text?: string | null
  body_html?: string | null
  category: string | null
  is_read?: boolean
  is_processed: boolean
  created_at?: string | null
}

function normalizeEmail(email: BackendEmail): Email {
  const receivedAt = email.date ?? email.created_at ?? new Date(0).toISOString()
  return {
    id: email.id,
    message_id: email.message_id,
    subject: email.subject ?? '',
    sender: email.sender ?? '',
    sender_email: email.sender ?? '',
    recipient: email.recipient ?? undefined,
    received_at: receivedAt,
    category: email.category,
    summary: null,
    processed: email.is_processed,
    content_text: email.body_text ?? undefined,
    content_html: email.body_html ?? undefined,
    is_read: email.is_read,
  }
}

export const emailApi = {
  getAll(params?: { skip?: number; limit?: number; category?: string; processed?: boolean }) {
    return unwrap<BackendEmail[]>(api.get<BackendEmail[]>('/emails', { params })).then((emails) =>
      emails.map(normalizeEmail),
    )
  },

  getById(id: string) {
    return unwrap<BackendEmail>(api.get<BackendEmail>(`/emails/${id}`)).then(normalizeEmail)
  },

  sync(data?: { days?: number; limit?: number }): Promise<SyncResponse> {
    return unwrap<SyncResponse>(api.post('/emails/sync', data))
  },

  parseAll(): Promise<ParseAllResponse> {
    return unwrap<ParseAllResponse>(api.post('/emails/parse-all'))
  },

  parseOne(id: string) {
    return api.post(`/emails/${id}/parse`)
  },
}

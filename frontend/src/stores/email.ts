import { create } from 'zustand'
import { emailApi } from '@/api/emails'
import type { Email, SyncResponse, ParseAllResponse } from '@/api/types'

interface EmailStore {
  emails: Email[]
  loading: boolean
  total: number
  fetchEmails: (params?: { skip?: number; limit?: number; category?: string; processed?: boolean }) => Promise<void>
  syncEmails: (data?: { days?: number; limit?: number }) => Promise<SyncResponse>
  parseAll: () => Promise<ParseAllResponse>
}

export const useEmailStore = create<EmailStore>((set) => ({
  emails: [],
  loading: false,
  total: 0,

  fetchEmails: async (params) => {
    set({ loading: true })
    try {
      const emails = await emailApi.getAll(params)
      set({ emails, total: emails.length })
    } finally {
      set({ loading: false })
    }
  },

  syncEmails: async (data) => {
    set({ loading: true })
    try {
      return await emailApi.sync(data)
    } finally {
      set({ loading: false })
    }
  },

  parseAll: async () => {
    set({ loading: true })
    try {
      return await emailApi.parseAll()
    } finally {
      set({ loading: false })
    }
  },
}))

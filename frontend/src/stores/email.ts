import { defineStore } from 'pinia'
import { ref } from 'vue'
import { emailApi } from '@/api/emails'
import type { Email } from '@/api/types'

export const useEmailStore = defineStore('email', () => {
  const emails = ref<Email[]>([])
  const loading = ref(false)
  const total = ref(0)

  async function fetchEmails(params?: { limit?: number; category?: string; processed?: boolean }) {
    loading.value = true
    try {
      emails.value = await emailApi.getAll(params)
      total.value = emails.value.length
    } finally {
      loading.value = false
    }
  }

  async function syncEmails(data?: { days?: number; limit?: number }) {
    loading.value = true
    try {
      const result = await emailApi.sync(data)
      return result
    } finally {
      loading.value = false
    }
  }

  async function parseAll() {
    loading.value = true
    try {
      const result = await emailApi.parseAll()
      return result
    } finally {
      loading.value = false
    }
  }

  return { emails, loading, total, fetchEmails, syncEmails, parseAll }
})

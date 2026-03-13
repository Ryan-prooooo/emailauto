<template>
  <div class="emails-page">
    <div class="header">
      <h1>邮件列表</h1>
    </div>

    <el-card>
      <div class="toolbar">
        <el-select v-model="categoryFilter" placeholder="选择分类" clearable @change="loadEmails">
          <el-option label="全部" value="" />
          <el-option label="购物" value="购物" />
          <el-option label="账单" value="账单" />
          <el-option label="物流" value="物流" />
          <el-option label="社交" value="社交" />
          <el-option label="工作" value="工作" />
          <el-option label="订阅" value="订阅" />
          <el-option label="其他" value="其他" />
        </el-select>
        <el-select v-model="processedFilter" placeholder="处理状态" clearable @change="loadEmails">
          <el-option label="全部" value="" />
          <el-option label="已处理" value="true" />
          <el-option label="待处理" value="false" />
        </el-select>
        <el-button @click="handleParseAll" :loading="parsing">解析全部</el-button>
      </div>

      <el-table :data="emails" v-loading="loading" style="width: 100%" @row-click="viewEmail">
        <el-table-column prop="subject" label="主题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="sender" label="发件人" width="180" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.category" :type="getTypeColor(row.category)">{{ row.category }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="received_at" label="时间" width="120">
          <template #default="{ row }">
            {{ formatDate(row.received_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="processed" label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.processed" type="success">已处理</el-tag>
            <el-tag v-else type="warning">待处理</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!emails.length && !loading" description="暂无邮件" />
    </el-card>

    <el-dialog v-model="detailVisible" title="邮件详情" width="800px">
      <div v-if="currentEmail" class="email-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="主题">{{ currentEmail.subject }}</el-descriptions-item>
          <el-descriptions-item label="发件人">{{ currentEmail.sender }}</el-descriptions-item>
          <el-descriptions-item label="收件人">{{ currentEmail.recipient }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ formatDateTime(currentEmail.received_at) }}</el-descriptions-item>
          <el-descriptions-item label="分类">
            <el-tag v-if="currentEmail.category" :type="getTypeColor(currentEmail.category)">{{ currentEmail.category }}</el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="摘要">{{ currentEmail.summary || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="email-content">
          <div class="content-header">邮件正文</div>
          <div class="content-body">{{ currentEmail.content_text || '无正文内容' }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="!currentEmail?.processed" type="primary" @click="parseEmail">解析邮件</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useEmailStore } from '@/stores/email'
import { emailApi } from '@/api/emails'
import type { Email } from '@/api/types'

const emailStore = useEmailStore()
const loading = ref(false)
const parsing = ref(false)
const categoryFilter = ref('')
const processedFilter = ref('')

const emails = ref<Email[]>([])
const detailVisible = ref(false)
const currentEmail = ref<Email | null>(null)

function getTypeColor(category: string): string {
  if (!category) return 'info'
  const PALETTE = ['', 'success', 'warning', 'danger', 'info', 'primary']
  let hash = 0
  for (let i = 0; i < category.length; i++) hash += category.charCodeAt(i)
  return PALETTE[Math.abs(hash) % PALETTE.length]
}

function formatDate(date: string) {
  return new Date(date).toLocaleDateString('zh-CN')
}

function formatDateTime(date: string) {
  return new Date(date).toLocaleString('zh-CN')
}

async function loadEmails() {
  loading.value = true
  try {
    const params: any = { limit: 50 }
    if (categoryFilter.value) {
      params.category = categoryFilter.value
    }
    if (processedFilter.value) {
      params.processed = processedFilter.value === 'true'
    }
    await emailStore.fetchEmails(params)
    emails.value = emailStore.emails
  } finally {
    loading.value = false
  }
}

function viewEmail(row: Email) {
  currentEmail.value = row
  detailVisible.value = true
}

async function handleParseAll() {
  parsing.value = true
  try {
    const result = await emailStore.parseAll()
    if (result?.processed) {
      ElMessage.success(`解析完成: ${result.processed}封`)
      await loadEmails()
    } else {
      ElMessage.error('解析失败')
    }
  } catch {
    ElMessage.error('解析失败')
  } finally {
    parsing.value = false
  }
}

async function parseEmail() {
  if (!currentEmail.value) return

  try {
    await emailApi.parseOne(currentEmail.value.id)
    ElMessage.success('解析成功')
    await loadEmails()
    detailVisible.value = false
  } catch {
    ElMessage.error('解析失败')
  }
}

onMounted(() => {
  loadEmails()
})
</script>

<style scoped>
.emails-page {
  padding: 24px;
}

.header {
  margin-bottom: 24px;
}

.header h1 {
  font-size: 24px;
  font-weight: 600;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.email-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.email-content {
  margin-top: 16px;
}

.content-header {
  font-weight: 600;
  margin-bottom: 8px;
}

.content-body {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>

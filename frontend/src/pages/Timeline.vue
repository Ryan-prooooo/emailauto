<template>
  <div class="timeline-page">
    <div class="header">
      <h1>时间线</h1>
      <el-button @click="handleSyncAndParse" :loading="syncing" type="primary">
        同步并解析
      </el-button>
    </div>

    <el-card>
      <div class="toolbar">
        <el-select v-model="typeFilter" placeholder="类型" clearable @change="loadData">
          <el-option label="全部" value="" />
          <el-option label="邮件" value="email" />
          <el-option label="事件" value="event" />
        </el-select>
        <el-select v-model="categoryFilter" placeholder="分类" clearable @change="loadData">
          <el-option label="全部" value="" />
          <el-option label="购物" value="购物" />
          <el-option label="账单" value="账单" />
          <el-option label="物流" value="物流" />
          <el-option label="社交" value="社交" />
          <el-option label="工作" value="工作" />
          <el-option label="订阅" value="订阅" />
          <el-option label="其他" value="其他" />
        </el-select>
        <el-select v-model="processedFilter" placeholder="处理状态" clearable @change="loadData">
          <el-option label="全部" value="" />
          <el-option label="已处理" value="true" />
          <el-option label="待处理" value="false" />
        </el-select>
      </div>

      <el-table :data="timelineData" v-loading="loading" style="width: 100%" @row-click="viewDetail">
        <el-table-column label="时间" width="150">
          <template #default="{ row }">
            <span class="time-text">{{ formatTime(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row._type === 'email' ? 'info' : 'primary'" size="small">
              {{ row._type === 'email' ? '邮件' : '事件' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="200">
          <template #default="{ row }">
            <div class="title-cell">
              <span class="title-text">{{ row._type === 'email' ? row.subject : row.title }}</span>
              <el-icon v-if="row._type === 'event' && row.important" color="#F59E0B"><Star /></el-icon>
              <el-icon v-if="row._type === 'event' && row.actionable" color="#10B981"><Clock /></el-icon>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="分类" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.category || row.event_type" :type="getTypeColor(row.category || row.event_type)" size="small">
              {{ row.category || row.event_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <template v-if="row._type === 'email'">
              <el-tag v-if="row.processed" type="success" size="small">已处理</el-tag>
              <el-tag v-else type="warning" size="small">待处理</el-tag>
            </template>
            <template v-else>
              <el-tag v-if="row.important" type="warning" size="small">重要</el-tag>
              <span v-else class="status-text">普通</span>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!timelineData.length && !loading" description="暂无数据" />
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="详情" width="700px">
      <div v-if="currentItem">
        <!-- 邮件详情 -->
        <template v-if="currentItem._type === 'email'">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="主题">{{ currentItem.subject }}</el-descriptions-item>
            <el-descriptions-item label="发件人">{{ currentItem.sender }}</el-descriptions-item>
            <el-descriptions-item label="收件人">{{ currentItem.recipient }}</el-descriptions-item>
            <el-descriptions-item label="时间">{{ formatDateTime(currentItem.received_at) }}</el-descriptions-item>
            <el-descriptions-item label="分类">
              <el-tag v-if="currentItem.category" :type="getTypeColor(currentItem.category)">{{ currentItem.category }}</el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="摘要">{{ currentItem.summary || '-' }}</el-descriptions-item>
          </el-descriptions>
          <div class="content-section">
            <div class="content-header">邮件正文</div>
            <div class="content-body">{{ currentItem.content_text || '无正文内容' }}</div>
          </div>
        </template>

        <!-- 事件详情 -->
        <template v-else>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="类型">
              <el-tag :type="getTypeColor(currentItem.event_type)">{{ currentItem.event_type }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="标题">{{ currentItem.title }}</el-descriptions-item>
            <el-descriptions-item label="描述">{{ currentItem.description || '-' }}</el-descriptions-item>
            <el-descriptions-item label="时间">{{ currentItem.event_time ? formatDateTime(currentItem.event_time) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="地点">{{ currentItem.location || '-' }}</el-descriptions-item>
            <el-descriptions-item label="重要">
              <el-tag v-if="currentItem.important" type="warning">重要</el-tag>
              <span v-else>普通</span>
            </el-descriptions-item>
            <el-descriptions-item label="可操作">
              <el-tag v-if="currentItem.actionable" type="success">待处理</el-tag>
              <span v-else>无</span>
            </el-descriptions-item>
            <el-descriptions-item v-if="currentItem.action_items" label="待办事项">
              {{ formatActionItems(currentItem.action_items) }}
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="currentItem?._type === 'email' && !currentItem?.processed" type="primary" @click="parseEmail">
          解析邮件
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Star, Clock } from '@element-plus/icons-vue'
import { useEmailStore } from '@/stores/email'
import { useEventStore } from '@/stores/event'
import { emailApi } from '@/api/emails'
import { systemApi } from '@/api/system'
import type { Email, Event } from '@/api/types'

const emailStore = useEmailStore()
const eventStore = useEventStore()

const loading = ref(false)
const syncing = ref(false)
const typeFilter = ref('')
const categoryFilter = ref('')
const processedFilter = ref('')

const emails = ref<Email[]>([])
const events = ref<Event[]>([])
const detailVisible = ref(false)
const currentItem = ref<(Email | Event) | null>(null)

type TimelineItem = (Email | Event) & { _type: 'email' | 'event' }

const timelineData = computed<TimelineItem[]>(() => {
  let items: TimelineItem[] = []

  // 转换邮件
  const filteredEmails = emails.value.filter(e => {
    if (typeFilter.value && typeFilter.value !== 'email') return false
    if (categoryFilter.value && e.category !== categoryFilter.value) return false
    if (processedFilter.value) {
      const processed = processedFilter.value === 'true'
      if (e.processed !== processed) return false
    }
    return true
  }).map(e => ({ ...e, _type: 'email' as const }))

  // 转换事件
  const filteredEvents = events.value.filter(e => {
    if (typeFilter.value && typeFilter.value !== 'event') return false
    if (categoryFilter.value && e.event_type !== categoryFilter.value) return false
    if (processedFilter.value) {
      const processed = processedFilter.value === 'true'
      // 事件：processed 字段存在，直接比较
      if (!!e.important !== processed) return false
    }
    return true
  }).map(e => ({ ...e, _type: 'event' as const }))

  items = [...filteredEmails, ...filteredEvents]

  // 按时间倒序排列
  items.sort((a, b) => {
    const timeA = a._type === 'email' ? a.received_at : (a.event_time || '')
    const timeB = b._type === 'email' ? b.received_at : (b.event_time || '')
    return timeB.localeCompare(timeA)
  })

  return items
})

function getTypeColor(type: string): string {
  if (!type) return 'info'
  const PALETTE = ['', 'success', 'warning', 'danger', 'info', 'primary']
  let hash = 0
  for (let i = 0; i < type.length; i++) hash += type.charCodeAt(i)
  return PALETTE[Math.abs(hash) % PALETTE.length]
}

function formatTime(row: TimelineItem): string {
  const timeStr = row._type === 'email' ? row.received_at : (row.event_time || '')
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatDateTime(date: string): string {
  return new Date(date).toLocaleString('zh-CN')
}

function formatActionItems(items: string): string {
  try {
    const arr = JSON.parse(items)
    return arr.join(', ')
  } catch {
    return items
  }
}

async function loadData() {
  loading.value = true
  try {
    await Promise.all([
      emailStore.fetchEmails({ limit: 500 }),
      eventStore.fetchEvents({ limit: 500 })
    ])
    emails.value = emailStore.emails
    events.value = eventStore.events
  } finally {
    loading.value = false
  }
}

function viewDetail(row: TimelineItem) {
  currentItem.value = row
  detailVisible.value = true
}

async function handleSyncAndParse() {
  syncing.value = true
  try {
    const result = await emailStore.syncEmails({ limit: 100 })
    if (result?.success) {
      ElMessage.success(`同步成功: ${result.new_emails || 0}封新邮件`)
    }
    const parseResult = await emailStore.parseAll()
    if (parseResult?.processed !== undefined) {
      ElMessage.success(`解析完成: ${parseResult.processed}封`)
    }
    await loadData()
  } catch {
    ElMessage.error('同步或解析失败')
  } finally {
    syncing.value = false
  }
}

async function parseEmail() {
  if (!currentItem.value || currentItem.value._type !== 'email') return
  try {
    await emailApi.parseOne(currentItem.value.id)
    ElMessage.success('解析成功')
    await loadData()
    detailVisible.value = false
  } catch {
    ElMessage.error('解析失败')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.timeline-page {
  padding: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.time-text {
  color: #909399;
  font-size: 13px;
}

.title-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.title-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-text {
  color: #909399;
  font-size: 13px;
}

.content-section {
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

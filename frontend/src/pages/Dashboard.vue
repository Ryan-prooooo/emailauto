<template>
  <div class="dashboard">
    <div class="header">
      <h1>仪表盘</h1>
      <el-button type="primary" @click="handleSync" :loading="syncing">
        <el-icon><Refresh /></el-icon>
        同步邮件
      </el-button>
    </div>

    <el-row :gutter="20" class="stats-grid">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-value">{{ emailStore.total }}</div>
            <div class="stat-label">总邮件数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-value">{{ eventStore.events.length }}</div>
            <div class="stat-label">提取事件数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-value">{{ eventStore.importantEvents.length }}</div>
            <div class="stat-label">重要事件</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-value">{{ pendingCount }}</div>
            <div class="stat-label">待处理</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="recent-events">
      <template #header>
        <div class="card-header">
          <span>最近事件</span>
          <el-button type="primary" link @click="$router.push('/timeline')">查看全部</el-button>
        </div>
      </template>
      <el-table :data="recentEvents" style="width: 100%" v-loading="loading">
        <el-table-column prop="event_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeColor(row.event_type)">{{ row.event_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="event_time" label="时间" width="180">
          <template #default="{ row }">
            {{ row.event_time ? formatDate(row.event_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="important" label="重要" width="80">
          <template #default="{ row }">
            <el-icon v-if="row.important" color="#F59E0B"><Star /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewEvent(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!recentEvents.length && !loading" description="暂无事件" />
    </el-card>

    <el-dialog v-model="detailVisible" title="事件详情" width="500px">
      <el-descriptions v-if="currentEvent" :column="1" border>
        <el-descriptions-item label="类型">
          <el-tag :type="getTypeColor(currentEvent.event_type)">{{ currentEvent.event_type }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="标题">{{ currentEvent.title }}</el-descriptions-item>
        <el-descriptions-item label="时间">
          {{ currentEvent.event_time ? formatDate(currentEvent.event_time) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="地点">{{ currentEvent.location || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Star } from '@element-plus/icons-vue'
import { useEmailStore } from '@/stores/email'
import { useEventStore } from '@/stores/event'
import { emailApi } from '@/api/emails'
import type { Event } from '@/api/types'

const emailStore = useEmailStore()
const eventStore = useEventStore()
const syncing = ref(false)
const loading = ref(false)
const detailVisible = ref(false)
const currentEvent = ref<Event | null>(null)

const recentEvents = computed(() => eventStore.events.slice(0, 5))

const pendingCount = computed(() => {
  return emailStore.emails.filter(e => !e.processed).length
})

function getTypeColor(type: string): string {
  if (!type) return 'info'
  const PALETTE = ['', 'success', 'warning', 'danger', 'info', 'primary']
  let hash = 0
  for (let i = 0; i < type.length; i++) hash += type.charCodeAt(i)
  return PALETTE[Math.abs(hash) % PALETTE.length]
}

function formatDate(date: string) {
  return new Date(date).toLocaleString('zh-CN')
}

function viewEvent(event: Event) {
  currentEvent.value = event
  detailVisible.value = true
}

async function handleSync() {
  syncing.value = true
  try {
    const result = await emailApi.sync({ days: 7, limit: 100 })
    if (result?.success) {
      ElMessage.success(`同步成功: ${result.synced}封`)
      await loadData()
    } else {
      ElMessage.error('同步失败')
    }
  } catch {
    ElMessage.error('同步失败')
  } finally {
    syncing.value = false
  }
}

async function loadData() {
  loading.value = true
  try {
    await Promise.all([
      emailStore.fetchEmails({ limit: 1000 }),
      eventStore.fetchEvents({ limit: 1000 })
    ])
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.dashboard {
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
}

.stats-grid {
  margin-bottom: 24px;
}

.stat-card {
  text-align: center;
  padding: 12px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #4F46E5;
}

.stat-label {
  font-size: 14px;
  color: #6B7280;
  margin-top: 4px;
}

.recent-events {
  margin-top: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
}
</style>

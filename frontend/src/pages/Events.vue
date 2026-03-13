<template>
  <div class="events-page">
    <div class="header">
      <h1>事件列表</h1>
    </div>

    <el-card>
      <div class="toolbar">
        <el-select v-model="typeFilter" placeholder="选择类型" clearable @change="loadEvents">
          <el-option label="全部" value="" />
          <el-option label="购物" value="购物" />
          <el-option label="账单" value="账单" />
          <el-option label="物流" value="物流" />
          <el-option label="社交" value="社交" />
          <el-option label="工作" value="工作" />
          <el-option label="订阅" value="订阅" />
          <el-option label="其他" value="其他" />
        </el-select>
        <el-checkbox v-model="importantOnly" @change="loadEvents">仅看重要</el-checkbox>
      </div>

      <el-table :data="events" v-loading="loading" style="width: 100%">
        <el-table-column prop="event_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeColor(row.event_type)">{{ row.event_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="event_time" label="时间" width="180">
          <template #default="{ row }">
            {{ row.event_time ? formatDate(row.event_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="location" label="地点" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.location || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="标记" width="120">
          <template #default="{ row }">
            <el-icon v-if="row.important" color="#F59E0B"><Star /></el-icon>
            <el-icon v-if="row.actionable" color="#10B981"><Clock /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!events.length && !loading" description="暂无事件" />
    </el-card>

    <el-dialog v-model="detailVisible" title="事件详情" width="600px">
      <el-descriptions v-if="currentEvent" :column="1" border>
        <el-descriptions-item label="类型">
          <el-tag :type="getTypeColor(currentEvent.event_type)">{{ currentEvent.event_type }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="标题">{{ currentEvent.title }}</el-descriptions-item>
        <el-descriptions-item label="描述">{{ currentEvent.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="时间">
          {{ currentEvent.event_time ? formatDate(currentEvent.event_time) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="地点">{{ currentEvent.location || '-' }}</el-descriptions-item>
        <el-descriptions-item label="重要">
          <el-tag v-if="currentEvent.important" type="warning">重要</el-tag>
          <span v-else>普通</span>
        </el-descriptions-item>
        <el-descriptions-item label="可操作">
          <el-tag v-if="currentEvent.actionable" type="success">待处理</el-tag>
          <span v-else>无</span>
        </el-descriptions-item>
        <el-descriptions-item v-if="currentEvent.action_items" label="待办事项">
          {{ formatActionItems(currentEvent.action_items) }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="sendNotification">发送通知</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Star, Clock } from '@element-plus/icons-vue'
import { useEventStore } from '@/stores/event'
import { systemApi } from '@/api/system'
import type { Event } from '@/api/types'

const eventStore = useEventStore()
const loading = ref(false)
const typeFilter = ref('')
const importantOnly = ref(false)

const events = ref<Event[]>([])
const detailVisible = ref(false)
const currentEvent = ref<Event | null>(null)

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

function formatActionItems(items: string) {
  try {
    const arr = JSON.parse(items)
    return arr.join(', ')
  } catch {
    return items
  }
}

async function loadEvents() {
  loading.value = true
  try {
    const params: any = { limit: 100 }
    if (typeFilter.value) {
      params.event_type = typeFilter.value
    }
    if (importantOnly.value) {
      params.important = true
    }
    await eventStore.fetchEvents(params)
    events.value = eventStore.events
  } finally {
    loading.value = false
  }
}

function viewDetail(event: Event) {
  currentEvent.value = event
  detailVisible.value = true
}

async function sendNotification() {
  if (!currentEvent.value) return

  try {
    await ElMessageBox.confirm('确定发送此事件的通知到邮箱吗？', '确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })

    await systemApi.sendDailySummary()
    ElMessage.success('发送成功')
    detailVisible.value = false
  } catch {
    // 用户取消
  }
}

onMounted(() => {
  loadEvents()
})
</script>

<style scoped>
.events-page {
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
</style>

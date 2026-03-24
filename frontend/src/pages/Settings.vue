<template>
  <div class="settings-page">
    <div class="header">
      <h1>设置</h1>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card class="settings-card">
          <template #header>
            <div class="card-header">
              <span>同步设置</span>
            </div>
          </template>
          <el-form label-width="120px">
            <el-form-item label="邮件检查间隔">
              <el-input-number v-model="settings.check_interval" :min="1" :max="60" />
              <span class="form-tip">分钟</span>
            </el-form-item>
            <el-form-item label="定时推送时间">
              <el-time-select
                v-model="scheduledTime"
                start="00:00"
                step="00:15"
                end="23:59"
                placeholder="选择时间"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveSettings" :loading="saving">
                保存设置
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="settings-card">
          <template #header>
            <div class="card-header">
              <span>分类标签</span>
            </div>
          </template>
          <div class="categories">
            <el-tag
              v-for="(cat, index) in settings.categories"
              :key="cat"
              :type="getTypeColor(index)"
              closable
              @close="removeCategory(cat)"
            >
              {{ cat }}
            </el-tag>
            <el-input
              v-if="inputVisible"
              ref="inputRef"
              v-model="inputValue"
              class="input-new-tag"
              size="small"
              @keyup.enter="handleInputConfirm"
              @blur="handleInputConfirm"
            />
            <el-button v-else size="small" @click="showInput">+ 新建分类</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="settings-card mt-20">
      <template #header>
        <div class="card-header">
          <span>连接测试</span>
        </div>
      </template>
      <el-button @click="testConnection" :loading="testing">
        <el-icon><Connection /></el-icon>
        测试 IMAP 连接
      </el-button>
      <el-result
        v-if="testResult"
        :icon="testResult.success ? 'success' : 'error'"
        :title="testResult.message"
      />
    </el-card>

    <el-card class="settings-card mt-20">
      <template #header>
        <div class="card-header">
          <span>手动操作</span>
        </div>
      </template>
      <el-space>
        <el-button type="primary" @click="handleSync" :loading="syncing">
          <el-icon><Refresh /></el-icon>
          立即同步
        </el-button>
        <el-button @click="handleParse" :loading="parsing">
          <el-icon><Document /></el-icon>
          解析全部邮件
        </el-button>
        <el-button @click="sendSummary" :loading="sending">
          <el-icon><Message /></el-icon>
          发送测试摘要
        </el-button>
      </el-space>
    </el-card>

    <el-card class="settings-card mt-20">
      <template #header>
        <div class="card-header">
          <span>定时任务状态</span>
        </div>
      </template>
      <el-table :data="jobs" v-loading="jobsLoading">
        <el-table-column prop="id" label="任务ID" width="150" />
        <el-table-column prop="name" label="任务名称" />
        <el-table-column prop="next_run_time" label="下次执行时间" />
      </el-table>
      <el-empty v-if="!jobs.length && !jobsLoading" description="暂无定时任务" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Refresh, Document, Message } from '@element-plus/icons-vue'
import { systemApi } from '@/api/system'

const settings = reactive({
  check_interval: 5,
  scheduled_send_hour: 9,
  scheduled_send_minute: 0,
  categories: [] as string[]
})

const scheduledTime = ref('09:00')
const saving = ref(false)
const testing = ref(false)
const testResult = ref<{ success: boolean; message: string } | null>(null)
const syncing = ref(false)
const parsing = ref(false)
const sending = ref(false)
const jobs = ref<any[]>([])
const jobsLoading = ref(false)

const inputVisible = ref(false)
const inputValue = ref('')
const inputRef = ref<HTMLInputElement>()

// 颜色数组，按索引循环分配不同颜色
const TAG_TYPES = ['', 'success', 'warning', 'danger', 'info', 'primary', 'success', 'warning']

function getTypeColor(index: number): string {
  return TAG_TYPES[index % TAG_TYPES.length]
}

async function loadSettings() {
  try {
    const data = await systemApi.getSettings()
    settings.check_interval = data.check_interval
    settings.scheduled_send_hour = data.scheduled_send_hour
    settings.scheduled_send_minute = data.scheduled_send_minute
    settings.categories = data.categories
    scheduledTime.value = `${String(data.scheduled_send_hour).padStart(2, '0')}:${String(data.scheduled_send_minute).padStart(2, '0')}`
  } catch (e) {
    console.error('加载设置失败', e)
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const [hour, minute] = scheduledTime.value.split(':').map(Number)
    settings.scheduled_send_hour = hour
    settings.scheduled_send_minute = minute
    await systemApi.updateSettings({
      check_interval: settings.check_interval,
      scheduled_send_hour: hour,
      scheduled_send_minute: minute,
      categories: settings.categories
    })
    ElMessage.success('设置已保存')
    await loadJobs()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const result = await systemApi.testConnection()
    testResult.value = { success: true, message: result.message || '连接成功' }
  } catch (e: any) {
    testResult.value = { success: false, message: e.detail || '连接失败' }
  } finally {
    testing.value = false
  }
}

async function handleSync() {
  syncing.value = true
  try {
    const result = await systemApi.triggerSync()
    if (result.success) {
      ElMessage.success(`同步成功: ${result.synced}封`)
    } else {
      ElMessage.error('同步失败')
    }
  } catch {
    ElMessage.error('同步失败')
  } finally {
    syncing.value = false
  }
}

async function handleParse() {
  parsing.value = true
  try {
    const result = await systemApi.triggerParse()
    ElMessage.success(`解析完成: ${result.processed}封`)
  } catch {
    ElMessage.error('解析失败')
  } finally {
    parsing.value = false
  }
}

async function sendSummary() {
  sending.value = true
  try {
    await systemApi.sendDailySummary()
    ElMessage.success('发送成功')
  } catch {
    ElMessage.error('发送失败')
  } finally {
    sending.value = false
  }
}

async function loadJobs() {
  jobsLoading.value = true
  try {
    jobs.value = await systemApi.getJobs()
  } catch {
    jobs.value = []
  } finally {
    jobsLoading.value = false
  }
}

function removeCategory(cat: string) {
  settings.categories = settings.categories.filter(c => c !== cat)
}

function showInput() {
  inputVisible.value = true
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function handleInputConfirm() {
  if (inputValue.value) {
    settings.categories.push(inputValue.value)
  }
  inputVisible.value = false
  inputValue.value = ''
}

onMounted(() => {
  loadSettings()
  loadJobs()
})
</script>

<style scoped>
.settings-page {
  padding: 24px;
}

.header {
  margin-bottom: 24px;
}

.header h1 {
  font-size: 24px;
  font-weight: 600;
}

.settings-card {
  margin-bottom: 20px;
}

.card-header {
  font-size: 16px;
  font-weight: 600;
}

.mt-20 {
  margin-top: 20px;
}

.form-tip {
  margin-left: 8px;
  color: #909399;
  font-size: 14px;
}

.categories {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.input-new-tag {
  width: 100px;
}
</style>

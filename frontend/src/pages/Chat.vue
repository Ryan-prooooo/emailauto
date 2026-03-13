<template>
  <div class="chat-page">
    <div class="chat-container">
      <!-- 左侧会话列表 -->
      <div class="sidebar">
        <div class="sidebar-header">
          <h3>对话历史</h3>
          <el-button size="small" @click="createNewSession">新建对话</el-button>
        </div>
        <div class="session-list">
          <div
            v-for="session in sessions"
            :key="session.id"
            :class="['session-item', { active: session.id === currentSessionId }]"
            @click="selectSession(session.id)"
          >
            <span class="session-title">{{ session.title }}</span>
            <el-button
              size="small"
              type="danger"
              link
              @click.stop="deleteSession(session.id)"
            >
              删除
            </el-button>
          </div>
          <el-empty v-if="!sessions.length" description="暂无对话" :image-size="60" />
        </div>
      </div>

      <!-- 右侧对话区域 -->
      <div class="chat-main">
        <div class="messages" ref="messagesRef">
          <div v-if="!currentSessionId" class="welcome">
            <h2>AI 邮件助手</h2>
            <p>可以问我关于邮件和事件的问题，例如：</p>
            <ul>
              <li>我最近有什么重要邮件？</li>
              <li>帮我总结一下上周的物流动态</li>
              <li>有哪些待处理的事件？</li>
            </ul>
          </div>

          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message', msg.role]"
          >
            <div class="message-avatar">
              <el-icon v-if="msg.role === 'user'"><User /></el-icon>
              <el-icon v-else><ChatDotRound /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-text">{{ msg.content }}</div>
              <div class="message-time">{{ formatTime(msg.created_at) }}</div>
            </div>
          </div>

          <div v-if="loading" class="message assistant">
            <div class="message-avatar">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-text loading">正在思考...</div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="2"
            placeholder="输入你的问题..."
            @keydown.enter.ctrl="sendMessage"
            :disabled="loading"
          />
          <el-button
            type="primary"
            :loading="loading"
            @click="sendMessage"
            :disabled="!inputMessage.trim()"
          >
            发送 (Ctrl+Enter)
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, ChatDotRound } from '@element-plus/icons-vue'
import { chatApi } from '@/api/chat'
import type { ChatSession, ChatMessage } from '@/api/types'

const sessions = ref<ChatSession[]>([])
const currentSessionId = ref<number | null>(null)
const messages = ref<ChatMessage[]>([])
const inputMessage = ref('')
const loading = ref(false)
const messagesRef = ref<HTMLElement>()

async function loadSessions() {
  try {
    sessions.value = await chatApi.getSessions()
  } catch (e) {
    console.error('加载会话失败', e)
  }
}

async function createNewSession() {
  try {
    const newSession = await chatApi.createSession()
    sessions.value.unshift(newSession)
    currentSessionId.value = newSession.id
    messages.value = []
    inputMessage.value = ''
    scrollToBottom()
  } catch (e) {
    ElMessage.error('创建对话失败')
  }
}

async function selectSession(sessionId: number) {
  currentSessionId.value = sessionId
  try {
    const res = await chatApi.getSession(sessionId)
    messages.value = res.messages
    scrollToBottom()
  } catch (e) {
    ElMessage.error('加载对话失败')
  }
}

async function deleteSession(sessionId: number) {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '提示', {
      type: 'warning'
    })
    await chatApi.deleteSession(sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
      messages.value = []
    }
    await loadSessions()
    ElMessage.success('删除成功')
  } catch (e) {
    // 用户取消
  }
}

async function sendMessage() {
  if (!inputMessage.value.trim() || loading.value) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  loading.value = true

  try {
    const res = await chatApi.sendMessage(currentSessionId.value, userMessage)
    currentSessionId.value = res.session_id
    messages.value = res.messages
    await loadSessions()
    scrollToBottom()
  } catch (e) {
    ElMessage.error('发送失败，请重试')
  } finally {
    loading.value = false
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function formatTime(time: string) {
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  loadSessions()
})
</script>

<style scoped>
.chat-page {
  height: 100%;
  padding: 0;
}

.chat-container {
  display: flex;
  height: calc(100vh - 120px);
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.sidebar {
  width: 260px;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.session-item:hover {
  background: #e4e7ed;
}

.session-item.active {
  background: #409eff;
  color: #fff;
}

.session-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.welcome {
  text-align: center;
  padding: 60px 20px;
  color: #909399;
}

.welcome h2 {
  color: #303133;
  margin-bottom: 16px;
}

.welcome ul {
  text-align: left;
  max-width: 300px;
  margin: 20px auto;
}

.welcome li {
  margin: 8px 0;
  color: #606266;
}

.message {
  display: flex;
  margin-bottom: 20px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.assistant .message-avatar {
  background: #67c23a;
}

.message-content {
  max-width: 70%;
  margin: 0 12px;
}

.message.user .message-content {
  text-align: right;
}

.message-text {
  padding: 12px 16px;
  border-radius: 8px;
  background: #f4f4f5;
  white-space: pre-wrap;
  word-break: break-word;
}

.message.user .message-text {
  background: #409eff;
  color: #fff;
}

.message-text.loading {
  color: #909399;
  font-style: italic;
}

.message-time {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.input-area {
  padding: 16px;
  border-top: 1px solid #e4e7ed;
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-area .el-input {
  flex: 1;
}
</style>

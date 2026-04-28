import { useEffect, useRef, useState } from 'react'
import { Avatar, Button, Card, Empty, Input, Space, Typography, message } from 'antd'
import { DeleteOutlined, RobotOutlined, SendOutlined, UserOutlined } from '@ant-design/icons'
import { useChatStore } from '@/stores/chat'

function formatTime(time: string) {
  return new Date(time).toLocaleString('zh-CN')
}

export default function Chat() {
  const {
    sessions,
    currentSessionId,
    messages,
    pendingAction,
    sending,
    fetchSessions,
    createSession,
    selectSession,
    deleteSession,
    sendMessage,
    resumeAction,
  } = useChatStore()

  const [inputText, setInputText] = useState('')
  const messagesRef = useRef<HTMLDivElement>(null)

  function scrollToBottom() {
    setTimeout(() => {
      messagesRef.current?.scrollTo({
        top: messagesRef.current.scrollHeight,
        behavior: 'smooth',
      })
    }, 50)
  }

  useEffect(() => {
    void fetchSessions()
  }, [fetchSessions])

  useEffect(() => {
    scrollToBottom()
  }, [messages, pendingAction])

  async function handleSend() {
    const text = inputText.trim()
    if (!text || sending) return
    setInputText('')
    try {
      await sendMessage(text)
      scrollToBottom()
    } catch {
      message.error('发送失败')
    }
  }

  async function handleCreateSession() {
    try {
      await createSession()
    } catch {
      message.error('创建会话失败')
    }
  }

  async function handleSelectSession(id: string) {
    try {
      await selectSession(id)
    } catch {
      message.error('加载会话失败')
    }
  }

  async function handleDeleteSession(id: string, event: React.MouseEvent) {
    event.stopPropagation()
    try {
      await deleteSession(id)
      message.success('已删除会话')
    } catch {
      message.error('删除会话失败')
    }
  }

  async function handleResume(confirmed: boolean) {
    try {
      await resumeAction(confirmed)
      message.success(confirmed ? '已确认执行' : '已取消操作')
    } catch {
      message.error('恢复执行失败')
    }
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 64px)', background: '#fff', overflow: 'hidden' }}>
      <div
        style={{
          width: 260,
          borderRight: '1px solid #e4e7ed',
          display: 'flex',
          flexDirection: 'column',
          background: '#f5f7fa',
        }}
      >
        <div
          style={{
            padding: 16,
            borderBottom: '1px solid #e4e7ed',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <h3 style={{ margin: 0, fontSize: 16 }}>会话列表</h3>
          <Button size="small" onClick={handleCreateSession}>
            新建
          </Button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
          {sessions.length === 0 ? (
            <Empty description="暂无会话" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => void handleSelectSession(session.id)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 12,
                  marginBottom: 4,
                  borderRadius: 6,
                  cursor: 'pointer',
                  background: session.id === currentSessionId ? '#409eff' : 'transparent',
                  color: session.id === currentSessionId ? '#fff' : 'inherit',
                  transition: 'background 0.2s',
                }}
              >
                <span
                  style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    flex: 1,
                  }}
                >
                  {session.title}
                </span>
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={(event) => void handleDeleteSession(session.id, event)}
                  style={{ color: session.id === currentSessionId ? '#fff' : undefined }}
                />
              </div>
            ))
          )}
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div ref={messagesRef} style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
          {!currentSessionId ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: '#909399' }}>
              <h2 style={{ color: '#303133', marginBottom: 16 }}>AI 邮件助手</h2>
              <p>你可以在这里查询邮件、总结时间线，或处理会议邀请。</p>
              <ul style={{ textAlign: 'left', maxWidth: 360, margin: '20px auto' }}>
                <li>最近有哪些重要邮件？</li>
                <li>帮我总结最新的订单更新。</li>
                <li>哪些会议邀请还需要我回复？</li>
              </ul>
            </div>
          ) : (
            <>
              {messages.map((msg, index) => (
                <div
                  key={`${msg.created_at}-${index}`}
                  style={{
                    display: 'flex',
                    marginBottom: 20,
                    flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                  }}
                >
                  <Avatar
                    icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                    style={{
                      background: msg.role === 'user' ? '#409eff' : '#67c23a',
                      flexShrink: 0,
                    }}
                  />
                  <div style={{ maxWidth: '70%', margin: '0 12px' }}>
                    <div
                      style={{
                        padding: '12px 16px',
                        borderRadius: 8,
                        background: msg.role === 'user' ? '#409eff' : '#f4f4f5',
                        color: msg.role === 'user' ? '#fff' : 'inherit',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      {msg.content}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: '#909399',
                        marginTop: 4,
                        textAlign: msg.role === 'user' ? 'right' : 'left',
                      }}
                    >
                      {formatTime(msg.created_at)}
                    </div>
                  </div>
                </div>
              ))}

              {pendingAction && (
                <Card style={{ maxWidth: 720, margin: '0 auto 20px', borderColor: '#f0b27a', background: '#fffaf3' }}>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <div>
                      <Typography.Title level={5} style={{ margin: 0 }}>
                        {pendingAction.title}
                      </Typography.Title>
                      <Typography.Text type="secondary">
                        {pendingAction.message}
                      </Typography.Text>
                    </div>
                    {typeof pendingAction.draft_content === 'string' && pendingAction.draft_content.trim() ? (
                      <Typography.Paragraph
                        style={{
                          marginBottom: 0,
                          whiteSpace: 'pre-wrap',
                          background: '#fff',
                          border: '1px solid #f0e0c0',
                          borderRadius: 8,
                          padding: 12,
                        }}
                      >
                        {pendingAction.draft_content}
                      </Typography.Paragraph>
                    ) : null}
                    <Space>
                      <Button type="primary" loading={sending} onClick={() => void handleResume(true)}>
                        确认
                      </Button>
                      <Button loading={sending} onClick={() => void handleResume(false)}>
                        取消
                      </Button>
                    </Space>
                  </Space>
                </Card>
              )}
            </>
          )}

          {sending && (
            <div style={{ display: 'flex', marginBottom: 20 }}>
              <Avatar icon={<RobotOutlined />} style={{ background: '#67c23a' }} />
              <div style={{ margin: '0 12px' }}>
                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: 8,
                    background: '#f4f4f5',
                    color: '#909399',
                    fontStyle: 'italic',
                  }}
                >
                  正在处理...
                </div>
              </div>
            </div>
          )}
        </div>

        <div
          style={{
            padding: '12px 16px',
            borderTop: '1px solid #e4e7ed',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            background: '#fafafa',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={sending}
              onClick={() => void handleSend()}
              disabled={!inputText.trim() || !!pendingAction}
            >
              发送
            </Button>
          </div>
          <Input.TextArea
            value={inputText}
            onChange={(event) => setInputText(event.target.value)}
            rows={3}
            placeholder={pendingAction ? '请先确认或取消当前待执行操作。' : '输入消息后按 Enter 发送，Shift + Enter 换行。'}
            onPressEnter={(event) => {
              if (!event.shiftKey) {
                event.preventDefault()
                void handleSend()
              }
            }}
            disabled={sending || !!pendingAction}
          />
        </div>
      </div>
    </div>
  )
}

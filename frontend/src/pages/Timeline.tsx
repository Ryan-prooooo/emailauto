import { useEffect, useMemo, useState } from 'react'
import { Card, Table, Button, Tag, Modal, Descriptions, Select, message } from 'antd'
import { StarOutlined } from '@ant-design/icons'
import { useEmailStore } from '@/stores/email'
import { useEventStore } from '@/stores/event'
import { emailApi } from '@/api/emails'
import type { Email, Event } from '@/api/types'

const TYPE_PALETTE = ['', 'success', 'warning', 'danger', 'info', 'primary']
const CATEGORY_OPTIONS = ['购物', '物流', 'meeting', '其他']

function getTypeColor(type: string): string {
  if (!type) return 'info'
  let hash = 0
  for (let i = 0; i < type.length; i++) hash += type.charCodeAt(i)
  return TYPE_PALETTE[Math.abs(hash) % TYPE_PALETTE.length]
}

function formatTime(timeStr: string): string {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDateTime(date: string): string {
  return new Date(date).toLocaleString('zh-CN')
}

type TimelineItem = (Email & { _type: 'email' }) | (Event & { _type: 'event' })

export default function Timeline() {
  const { emails, fetchEmails } = useEmailStore()
  const { events, fetchEvents } = useEventStore()
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [typeFilter, setTypeFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [processedFilter, setProcessedFilter] = useState('')
  const [detailVisible, setDetailVisible] = useState(false)
  const [currentItem, setCurrentItem] = useState<TimelineItem | null>(null)

  const timelineData: TimelineItem[] = useMemo(() => {
    const filteredEmails = emails
      .filter((email) => {
        if (typeFilter && typeFilter !== 'email') return false
        if (categoryFilter && email.category !== categoryFilter) return false
        if (processedFilter) {
          const processed = processedFilter === 'true'
          if (email.processed !== processed) return false
        }
        return true
      })
      .map((email) => ({ ...email, _type: 'email' as const }))

    const filteredEvents = events
      .filter((event) => {
        if (typeFilter && typeFilter !== 'event') return false
        if (categoryFilter && event.event_type !== categoryFilter) return false
        return true
      })
      .map((event) => ({ ...event, _type: 'event' as const }))

    const items: TimelineItem[] = [...filteredEmails, ...filteredEvents]
    items.sort((a, b) => {
      const timeA = a._type === 'email' ? a.received_at : (a.event_time || '')
      const timeB = b._type === 'email' ? b.received_at : (b.event_time || '')
      return timeB.localeCompare(timeA)
    })
    return items
  }, [emails, events, typeFilter, categoryFilter, processedFilter])

  async function loadData() {
    setLoading(true)
    try {
      await Promise.all([fetchEmails({ limit: 500 }), fetchEvents({ limit: 500 })])
    } finally {
      setLoading(false)
    }
  }

  async function handleSyncAndParse() {
    setSyncing(true)
    try {
      const syncResult = await emailApi.sync({ limit: 100 })
      if (syncResult.success) {
        message.success(`同步成功：新增 ${syncResult.synced} 封邮件`)
      }
      const parseResult = await emailApi.parseAll()
      message.success(`解析完成：${parseResult.processed} 封邮件`)
      await loadData()
    } catch {
      message.error('同步或解析失败')
    } finally {
      setSyncing(false)
    }
  }

  function viewDetail(row: TimelineItem) {
    setCurrentItem(row)
    setDetailVisible(true)
  }

  async function parseEmail() {
    if (!currentItem || currentItem._type !== 'email') return
    try {
      await emailApi.parseOne(currentItem.id)
      message.success('解析成功')
      await loadData()
      setDetailVisible(false)
    } catch {
      message.error('解析失败')
    }
  }

  useEffect(() => {
    async function initialize() {
      setLoading(true)
      try {
        await Promise.all([fetchEmails({ limit: 500 }), fetchEvents({ limit: 500 })])
      } finally {
        setLoading(false)
      }
    }

    void initialize()
  }, [fetchEmails, fetchEvents])

  const columns = [
    {
      title: '时间',
      dataIndex: 'received_at',
      key: 'time',
      width: 150,
      render: (_: unknown, row: TimelineItem) => (
        <span style={{ color: '#909399', fontSize: 13 }}>
          {formatTime(row._type === 'email' ? row.received_at : (row.event_time || ''))}
        </span>
      ),
    },
    {
      title: '类型',
      dataIndex: '_type',
      key: 'type',
      width: 80,
      render: (type: 'email' | 'event') => (
        <Tag color={type === 'email' ? 'default' : 'processing'}>
          {type === 'email' ? '邮件' : '事件'}
        </Tag>
      ),
    },
    {
      title: '标题',
      key: 'title',
      minWidth: 200,
      render: (_: unknown, row: TimelineItem) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {row._type === 'email' ? row.subject : row.title}
          </span>
          {row._type === 'event' && row.important && <StarOutlined style={{ color: '#F59E0B' }} />}
        </div>
      ),
    },
    {
      title: '分类',
      key: 'category',
      width: 100,
      render: (_: unknown, row: TimelineItem) => {
        const category = row._type === 'email' ? row.category : row.event_type
        return category ? <Tag color={getTypeColor(category)}>{category}</Tag> : null
      },
    },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_: unknown, row: TimelineItem) => {
        if (row._type === 'email') {
          return row.processed ? <Tag color="success">已处理</Tag> : <Tag color="warning">待处理</Tag>
        }
        return row.important ? <Tag color="warning">重要</Tag> : (
          <span style={{ color: '#909399', fontSize: 13 }}>普通</span>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, row: TimelineItem) => (
        <Button type="link" size="small" onClick={() => viewDetail(row)}>
          详情
        </Button>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>时间线</h1>
        <Button type="primary" loading={syncing} onClick={handleSyncAndParse}>
          同步并解析
        </Button>
      </div>

      <Card style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          <Select
            placeholder="类型"
            allowClear
            value={typeFilter || undefined}
            onChange={(value) => setTypeFilter(value || '')}
            style={{ width: 120 }}
          >
            <Select.Option value="">全部</Select.Option>
            <Select.Option value="email">邮件</Select.Option>
            <Select.Option value="event">事件</Select.Option>
          </Select>
          <Select
            placeholder="分类"
            allowClear
            value={categoryFilter || undefined}
            onChange={(value) => setCategoryFilter(value || '')}
            style={{ width: 140 }}
          >
            <Select.Option value="">全部</Select.Option>
            {CATEGORY_OPTIONS.map((category) => (
              <Select.Option key={category} value={category}>
                {category}
              </Select.Option>
            ))}
          </Select>
          <Select
            placeholder="处理状态"
            allowClear
            value={processedFilter || undefined}
            onChange={(value) => setProcessedFilter(value || '')}
            style={{ width: 140 }}
          >
            <Select.Option value="">全部</Select.Option>
            <Select.Option value="true">已处理</Select.Option>
            <Select.Option value="false">待处理</Select.Option>
          </Select>
        </div>

        <Table
          dataSource={timelineData}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={false}
          onRow={(record) => ({
            style: { cursor: 'pointer' },
            onClick: () => viewDetail(record),
          })}
          locale={{ emptyText: '暂无数据' }}
        />
      </Card>

      <Modal
        title="详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={(
          <div>
            <Button onClick={() => setDetailVisible(false)}>关闭</Button>
            {currentItem?._type === 'email' && !currentItem.processed && (
              <Button type="primary" onClick={parseEmail} style={{ marginLeft: 8 }}>
                解析邮件
              </Button>
            )}
          </div>
        )}
      >
        {currentItem && (
          <>
            {currentItem._type === 'email' ? (
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="主题">{currentItem.subject}</Descriptions.Item>
                <Descriptions.Item label="发件人">{currentItem.sender}</Descriptions.Item>
                <Descriptions.Item label="收件人">{currentItem.recipient || '-'}</Descriptions.Item>
                <Descriptions.Item label="时间">{formatDateTime(currentItem.received_at)}</Descriptions.Item>
                <Descriptions.Item label="分类">
                  {currentItem.category ? (
                    <Tag color={getTypeColor(currentItem.category)}>{currentItem.category}</Tag>
                  ) : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="摘要">{currentItem.summary || '-'}</Descriptions.Item>
                <Descriptions.Item label="邮件正文">
                  <div
                    style={{
                      maxHeight: 300,
                      overflowY: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      background: '#f5f7fa',
                      padding: 12,
                      borderRadius: 4,
                    }}
                  >
                    {currentItem.content_text || '暂无正文内容'}
                  </div>
                </Descriptions.Item>
              </Descriptions>
            ) : (
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="类型">
                  <Tag color={getTypeColor(currentItem.event_type)}>{currentItem.event_type || '未分类'}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="标题">{currentItem.title}</Descriptions.Item>
                <Descriptions.Item label="描述">{currentItem.description || '-'}</Descriptions.Item>
                <Descriptions.Item label="时间">
                  {currentItem.event_time ? formatDateTime(currentItem.event_time) : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="地点">{currentItem.location || '-'}</Descriptions.Item>
                <Descriptions.Item label="重要性">
                  {currentItem.important ? <Tag color="warning">重要</Tag> : '普通'}
                </Descriptions.Item>
                <Descriptions.Item label="可操作">
                  {currentItem.actionable ? <Tag color="success">待处理</Tag> : '无'}
                </Descriptions.Item>
              </Descriptions>
            )}
          </>
        )}
      </Modal>
    </div>
  )
}

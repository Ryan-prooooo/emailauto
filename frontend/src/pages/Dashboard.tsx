import { useEffect, useState } from 'react'
import { Row, Col, Card, Statistic, Table, Button, Tag, Modal, Descriptions, message } from 'antd'
import { ReloadOutlined, StarOutlined } from '@ant-design/icons'
import { useEmailStore } from '@/stores/email'
import { useEventStore } from '@/stores/event'
import { emailApi } from '@/api/emails'
import type { Event } from '@/api/types'

const TYPE_PALETTE = ['', 'success', 'warning', 'danger', 'info', 'primary']

function getTypeColor(type: string): string {
  if (!type) return 'info'
  let hash = 0
  for (let i = 0; i < type.length; i++) hash += type.charCodeAt(i)
  return TYPE_PALETTE[Math.abs(hash) % TYPE_PALETTE.length]
}

function formatDate(date: string) {
  return new Date(date).toLocaleString('zh-CN')
}

export default function Dashboard() {
  const { emails, fetchEmails } = useEmailStore()
  const { events, fetchEvents } = useEventStore()
  const [syncing, setSyncing] = useState(false)
  const [loading, setLoading] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [currentEvent, setCurrentEvent] = useState<Event | null>(null)

  const recentEvents = events.slice(0, 5)
  const pendingCount = emails.filter((email) => !email.processed).length

  async function loadData() {
    setLoading(true)
    try {
      await Promise.all([fetchEmails({ limit: 1000 }), fetchEvents({ limit: 1000 })])
    } finally {
      setLoading(false)
    }
  }

  async function handleSync() {
    setSyncing(true)
    try {
      const result = await emailApi.sync({ days: 7, limit: 100 })
      if (result.success) {
        message.success(`同步成功：新增 ${result.synced} 封邮件`)
      } else {
        message.error('同步失败')
      }
      await loadData()
    } catch {
      message.error('同步失败')
    } finally {
      setSyncing(false)
    }
  }

  function viewEvent(event: Event) {
    setCurrentEvent(event)
    setDetailVisible(true)
  }

  useEffect(() => {
    async function initialize() {
      setLoading(true)
      try {
        await Promise.all([fetchEmails({ limit: 1000 }), fetchEvents({ limit: 1000 })])
      } finally {
        setLoading(false)
      }
    }

    void initialize()
  }, [fetchEmails, fetchEvents])

  const eventColumns = [
    {
      title: '类型',
      dataIndex: 'event_type',
      key: 'event_type',
      width: 100,
      render: (type: string) => <Tag color={getTypeColor(type)}>{type || '未分类'}</Tag>,
    },
    { title: '标题', dataIndex: 'title', key: 'title' },
    {
      title: '时间',
      dataIndex: 'event_time',
      key: 'event_time',
      width: 180,
      render: (time: string) => (time ? formatDate(time) : '-'),
    },
    {
      title: '重要',
      dataIndex: 'important',
      key: 'important',
      width: 80,
      render: (important: boolean) => (important ? <StarOutlined style={{ color: '#F59E0B' }} /> : null),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: Event) => (
        <Button type="link" onClick={() => viewEvent(record)}>
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
        <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>仪表盘</h1>
        <Button type="primary" icon={<ReloadOutlined />} loading={syncing} onClick={handleSync}>
          同步邮件
        </Button>
      </div>

      <Row gutter={20} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card hoverable>
            <Statistic title="邮件总数" value={emails.length} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable>
            <Statistic title="提取事件数" value={events.length} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable>
            <Statistic title="重要事件" value={events.filter((event) => event.important).length} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable>
            <Statistic title="待处理邮件" value={pendingCount} />
          </Card>
        </Col>
      </Row>

      <Card
        title="最近事件"
        extra={(
          <Button type="link" onClick={() => { window.location.hash = '#/timeline' }}>
            查看全部
          </Button>
        )}
      >
        <Table
          dataSource={recentEvents}
          columns={eventColumns}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{ emptyText: '暂无事件' }}
        />
      </Card>

      <Modal
        title="事件详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={<Button onClick={() => setDetailVisible(false)}>关闭</Button>}
      >
        {currentEvent && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="类型">
              <Tag color={getTypeColor(currentEvent.event_type)}>{currentEvent.event_type || '未分类'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="标题">{currentEvent.title}</Descriptions.Item>
            <Descriptions.Item label="时间">
              {currentEvent.event_time ? formatDate(currentEvent.event_time) : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="地点">{currentEvent.location || '-'}</Descriptions.Item>
            <Descriptions.Item label="状态">{currentEvent.status || '-'}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}

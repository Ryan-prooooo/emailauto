import { useEffect, useState } from 'react'
import { Button, Card, Form, Input, InputNumber, Result, Space, Table, Tag, message } from 'antd'
import { CheckCircleOutlined, FileTextOutlined, MailOutlined, ReloadOutlined } from '@ant-design/icons'

import { systemApi } from '@/api/system'
import type { Job } from '@/api/types'

const TAG_TYPES = ['', 'success', 'warning', 'danger', 'info', 'primary', 'success', 'warning']

function getTypeColor(index: number): string {
  return TAG_TYPES[index % TAG_TYPES.length]
}

interface TestResult {
  success: boolean
  message: string
}

export default function Settings() {
  const [form] = Form.useForm()
  const [categories, setCategories] = useState<string[]>([])
  const [inputVisible, setInputVisible] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [parsing, setParsing] = useState(false)
  const [sending, setSending] = useState(false)
  const [jobs, setJobs] = useState<Job[]>([])
  const [jobsLoading, setJobsLoading] = useState(false)

  async function saveSettings() {
    setSaving(true)
    try {
      const values = form.getFieldsValue()
      await systemApi.updateSettings({
        check_interval: values.check_interval,
        scheduled_send_hour: values.scheduled_send_hour,
        scheduled_send_minute: values.scheduled_send_minute,
        categories,
      })
      message.success('设置已保存')
      await loadJobs()
    } catch {
      message.error('保存设置失败')
    } finally {
      setSaving(false)
    }
  }

  async function testConnection() {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await systemApi.testConnection()
      setTestResult({ success: true, message: result.message || '连接成功' })
    } catch (error: unknown) {
      const err = error as { detail?: string }
      setTestResult({ success: false, message: err.detail || '连接失败' })
    } finally {
      setTesting(false)
    }
  }

  async function handleSync() {
    setSyncing(true)
    try {
      const result = await systemApi.triggerSync()
      if (result.success) {
        message.success(`同步完成：新增 ${result.synced} 封邮件`)
      } else {
        message.error('同步失败')
      }
    } catch {
      message.error('同步失败')
    } finally {
      setSyncing(false)
    }
  }

  async function handleParse() {
    setParsing(true)
    try {
      const result = await systemApi.triggerParse()
      message.success(`解析完成：${result.processed} 封邮件`)
    } catch {
      message.error('解析失败')
    } finally {
      setParsing(false)
    }
  }

  async function sendSummary() {
    setSending(true)
    try {
      await systemApi.sendDailySummary()
      message.success('测试摘要已发送')
    } catch {
      message.error('发送测试摘要失败')
    } finally {
      setSending(false)
    }
  }

  async function loadJobs() {
    setJobsLoading(true)
    try {
      const data = await systemApi.getJobs()
      setJobs(Array.isArray(data) ? data : [])
    } catch {
      setJobs([])
    } finally {
      setJobsLoading(false)
    }
  }

  function removeCategory(category: string) {
    setCategories((prev) => prev.filter((item) => item !== category))
  }

  function handleInputConfirm() {
    const nextValue = inputValue.trim()
    if (nextValue) {
      setCategories((prev) => [...prev, nextValue])
    }
    setInputVisible(false)
    setInputValue('')
  }

  useEffect(() => {
    async function initialize() {
      try {
        const data = await systemApi.getSettings()
        form.setFieldsValue({
          check_interval: data.check_interval,
          scheduled_send_hour: data.scheduled_send_hour,
          scheduled_send_minute: data.scheduled_send_minute,
        })
        setCategories(data.categories || [])
      } catch (error) {
        console.error('Failed to load settings', error)
      }

      await loadJobs()
    }

    void initialize()
  }, [form])

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 24 }}>设置</h1>

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 16 }}>同步设置</h3>
        <Form form={form} layout="vertical">
          <Form.Item label="检查间隔" name="check_interval">
            <InputNumber min={1} max={60} addonAfter="分钟" />
          </Form.Item>
          <Form.Item label="每日摘要时间">
            <Space>
              <Form.Item name="scheduled_send_hour" noStyle>
                <InputNumber min={0} max={23} placeholder="小时" />
              </Form.Item>
              <Form.Item name="scheduled_send_minute" noStyle>
                <InputNumber min={0} max={59} placeholder="分钟" />
              </Form.Item>
            </Space>
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={saveSettings} loading={saving}>
              保存设置
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 16 }}>分类</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {categories.map((category, index) => (
            <Tag
              key={category}
              color={getTypeColor(index)}
              closable
              onClose={() => removeCategory(category)}
            >
              {category}
            </Tag>
          ))}
          {inputVisible ? (
            <Input
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onPressEnter={handleInputConfirm}
              onBlur={handleInputConfirm}
              style={{ width: 120 }}
              autoFocus
            />
          ) : (
            <Button size="small" onClick={() => setInputVisible(true)}>
              + 添加分类
            </Button>
          )}
        </div>
      </Card>

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 16 }}>连接测试</h3>
        <Button icon={<CheckCircleOutlined />} onClick={testConnection} loading={testing}>
          测试 IMAP 连接
        </Button>
        {testResult && (
          <Result
            status={testResult.success ? 'success' : 'error'}
            title={testResult.message}
            style={{ marginTop: 16, padding: 0 }}
          />
        )}
      </Card>

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 16 }}>手动操作</h3>
        <Space>
          <Button type="primary" icon={<ReloadOutlined />} loading={syncing} onClick={handleSync}>
            立即同步
          </Button>
          <Button icon={<FileTextOutlined />} loading={parsing} onClick={handleParse}>
            解析全部邮件
          </Button>
          <Button icon={<MailOutlined />} loading={sending} onClick={sendSummary}>
            发送测试摘要
          </Button>
        </Space>
      </Card>

      <Card title="定时任务">
        <Table
          dataSource={jobs}
          rowKey="id"
          loading={jobsLoading}
          pagination={false}
          locale={{ emptyText: '暂无定时任务' }}
          columns={[
            { title: '任务 ID', dataIndex: 'id', key: 'id' },
            { title: '任务名称', dataIndex: 'name', key: 'name' },
            { title: '下次执行时间', dataIndex: 'next_run_time', key: 'next_run_time' },
          ]}
        />
      </Card>
    </div>
  )
}

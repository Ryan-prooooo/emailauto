import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Layout as AntLayout, Menu, Badge, Avatar, Dropdown } from 'antd'
import {
  MessageOutlined,
  DashboardOutlined,
  ClockCircleOutlined,
  SettingOutlined,
  BellOutlined,
  UserOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'

const { Sider, Header, Content } = AntLayout

const menuItems: MenuProps['items'] = [
  { key: '/chat', icon: <MessageOutlined />, label: 'AI 对话' },
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/timeline', icon: <ClockCircleOutlined />, label: '时间线' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
]

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()

  const userMenuItems: MenuProps['items'] = [
    { key: 'logout', label: '退出登录' },
  ]

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider width={220} style={{ background: '#304156' }}>
        <div
          style={{
            height: 60,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            fontSize: 18,
            fontWeight: 600,
            color: '#fff',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          <MessageOutlined style={{ fontSize: 24 }} />
          <span>邮件助手</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ background: 'transparent', borderRight: 0 }}
        />
      </Sider>

      <AntLayout>
        <Header
          style={{
            background: '#fff',
            boxShadow: '0 1px 4px rgba(0, 21, 41, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            padding: '0 20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Badge count={0} size="small">
              <BellOutlined style={{ fontSize: 18, cursor: 'pointer', color: '#606266' }} />
            </Badge>
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  cursor: 'pointer',
                  color: '#606266',
                }}
              >
                <Avatar size="small" icon={<UserOutlined />} />
                <span>user@qq.com</span>
              </div>
            </Dropdown>
          </div>
        </Header>
        <Content style={{ background: '#f0f2f5', padding: 0 }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  )
}

import { Navigate, createBrowserRouter } from 'react-router-dom'
import Layout from '@/pages/Layout'
import Dashboard from '@/pages/Dashboard'
import Timeline from '@/pages/Timeline'
import Chat from '@/pages/Chat'
import Settings from '@/pages/Settings'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/chat" replace /> },
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'timeline', element: <Timeline /> },
      { path: 'chat', element: <Chat /> },
      { path: 'settings', element: <Settings /> },
    ],
  },
])

import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/pages/Layout.vue'),
    children: [
      {
        path: '',
        redirect: '/chat'
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/pages/Dashboard.vue')
      },
      {
        path: 'emails',
        name: 'Emails',
        component: () => import('@/pages/Emails.vue')
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/pages/Chat.vue')
      },
      {
        path: 'events',
        name: 'Events',
        component: () => import('@/pages/Events.vue')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/pages/Settings.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router

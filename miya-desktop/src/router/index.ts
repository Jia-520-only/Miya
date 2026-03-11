import { createRouter, createWebHashHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    redirect: '/chat'
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@views/ChatView.vue')
  },
  {
    path: '/live2d',
    name: 'Live2D',
    component: () => import('@views/Live2DStandalone.vue')
  },
  {
    path: '/code',
    name: 'Code',
    component: () => import('@views/CodeView.vue')
  },
  {
    path: '/monitor',
    name: 'Monitor',
    component: () => import('@views/MonitorView.vue')
  },
  {
    path: '/terminal',
    name: 'Terminal',
    component: () => import('@views/TerminalView.vue')
  },
  {
    path: '/files',
    name: 'Files',
    component: () => import('@views/FilesView.vue')
  },
  {
    path: '/analytics',
    name: 'Analytics',
    component: () => import('@views/AnalyticsView.vue')
  },
  {
    path: '/research',
    name: 'Research',
    component: () => import('@views/ResearchView.vue')
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@views/TasksView.vue')
  },
  {
    path: '/tools',
    name: 'Tools',
    component: () => import('@views/ToolsView.vue')
  },
  {
    path: '/processes',
    name: 'Processes',
    component: () => import('@views/ProcessesView.vue')
  },
  {
    path: '/iot',
    name: 'IoT',
    component: () => import('@views/IoTView.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@views/SettingsView.vue')
  },
  {
    path: '/about',
    name: 'About',
    component: () => import('@views/AboutView.vue')
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router

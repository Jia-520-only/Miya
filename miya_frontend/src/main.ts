import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import { initComponentColors } from '@/composables/useComponentColors'
import App from './App.vue'
import './style.css'
import 'virtual:uno.css'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: () => import('@/views/PanelView.vue') },
    { path: '/chat', component: () => import('@/views/MessageView.vue') },
    { path: '/mind', component: () => import('@/views/MindView.vue') },
    { path: '/config', component: () => import('@/views/ConfigView.vue') },
    { path: '/float', component: () => import('@/views/FloatingView.vue') },
    { path: '/screen', component: () => import('@/views/ScreenVisionView.vue') },
    { path: '/platforms', component: () => import('@/views/PlatformsView.vue') },
    { path: '/console', component: () => import('@/views/ConsoleView.vue') },
    { path: '/inbox', component: () => import('@/views/MessageInbox.vue') },
    { path: '/terminal', component: () => import('@/views/TerminalView.vue') },
    { path: '/dsh-web', component: () => import('@/views/DshWebView.vue') },
    { path: '/artboard', component: () => import('@/views/ArtboardView.vue') },
    { path: '/hub', component: () => import('@/views/HubView.vue') },
    { path: '/community', component: () => import('@/views/CommunityView.vue') },
    { path: '/earth', component: () => import('@/views/EarthOnlineView.vue') },
  ],
})

createApp(App)
  .use(router)
  .mount('#app')

initComponentColors()

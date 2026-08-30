"""
Miya Dashboard - WebUI (Simplified AstrBot Theme)

This is a simplified dashboard inspired by AstrBot's design patterns.
"""

import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { createStore } from 'pinia'
import App from './App.vue'
import router from './router'
import store from './stores'
import './styles/main.scss'

const app = createApp(App)
app.use(store)
app.use(router)
app.mount('#app')

export { app, router, store }
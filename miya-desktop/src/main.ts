import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import PrimeVue from 'primevue/config'

// 导入 PrimeVue 样式 - 使用 PrimeVue 3.x 兼容的方式
import 'primevue/resources/themes/aura-dark-blue/theme.css'
import 'primeicons/primeicons.css'

const app = createApp(App)

// 安装 Pinia
const pinia = createPinia()
app.use(pinia)

// 安装路由
app.use(router)

// 安装 PrimeVue
app.use(PrimeVue)

app.mount('#app')

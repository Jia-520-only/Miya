import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'

// 配置基础 URL
const BASE_URL = 'http://localhost:8000/api'

// 创建 axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 添加认证 token（如果需要）
    const token = localStorage.getItem('miya-token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error)

    // 处理常见错误
    if (error.response) {
      switch (error.response.status) {
        case 401:
          // 未授权
          console.error('Unauthorized access')
          break
        case 404:
          console.error('Resource not found')
          break
        case 500:
          console.error('Server error')
          break
        default:
          console.error(`HTTP Error: ${error.response.status}`)
      }
    } else if (error.request) {
      // 请求已发送但没有响应
      console.error('No response received')
    } else {
      // 请求配置错误
      console.error('Request configuration error')
    }

    return Promise.reject(error)
  }
)

export default apiClient

import type { AxiosError, AxiosInstance } from 'axios'
import type { MaybeRef } from 'vue'
import axios from 'axios'
import camelcaseKeys from 'camelcase-keys'
import snakecaseKeys from 'snakecase-keys'
import { unref, watch } from 'vue'

export class ApiClient {
  instance: AxiosInstance

  get endpoint() {
    return `http://localhost:${unref(this.port)}`
  }

  constructor(readonly port: MaybeRef<number>) {
    this.instance = axios.create({
      baseURL: this.endpoint,
      timeout: 120 * 1000,
      headers: { 'Content-Type': 'application/json' },
      transformRequest(data) {
        if (
          data
          && typeof data === 'object'
          && !(data instanceof FormData)
          && !(data instanceof ArrayBuffer)
          && !(data instanceof Blob)
        ) {
          return JSON.stringify(snakecaseKeys(data, { deep: true }))
        }
        return data
      },
      transformResponse(data) {
        return camelcaseKeys(JSON.parse(data), { deep: true })
      },
    })

    watch(() => this.endpoint, (endpoint) => {
      this.instance.defaults.baseURL = endpoint
    })

    this.instance.interceptors.response.use(
      response => response.data,
      this.handleResponseError.bind(this),
    )
  }

  private async handleResponseError(error: AxiosError & { config: { _retry?: boolean } }): Promise<any> {
    if (!error.config) {
      return Promise.reject(error)
    }

    const status = error.response?.status
    const url = error.config?.url || ''
    const isExpectedMissingSession = status === 404 && !!url.match(/\/sessions\/[^/]+$/)
    const isExpectedHealthNetworkError = !status && url.startsWith('/health')
    const isExpectedBootstrapConfigNetworkError = !status && url.startsWith('/system/config')

    if (
      !isExpectedMissingSession
      && !isExpectedHealthNetworkError
      && !isExpectedBootstrapConfigNetworkError
    ) {
      console.error('API Error:', error)
    }
    return Promise.reject(error)
  }
}

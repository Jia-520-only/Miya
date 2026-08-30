import { getApiPort } from './api-port'

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `http://localhost:${getApiPort()}${normalizedPath}`
}

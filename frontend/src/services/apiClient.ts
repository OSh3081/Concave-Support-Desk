import axios from 'axios'
import { clearAccessToken, getAccessToken } from './auth.service'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL?.trim() || 'http://localhost:8000/api',
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.set('Authorization', `Bearer ${token}`)
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      // A failed login is a form error. Other 401s invalidate the stored session.
      if (!error.config?.url?.includes('/auth/login')) {
        clearAccessToken()
        if (typeof window !== 'undefined') window.dispatchEvent(new Event('concave:session-expired'))
      }
    }
    return Promise.reject(error)
  },
)

/** Converts an API failure into a useful message while keeping error handling outside UI components. */
export function getApiErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error ? error.message : 'An unexpected error occurred.'
  }

  const data = error.response?.data as { detail?: unknown; message?: unknown } | undefined
  if (typeof data?.detail === 'string') return data.detail
  if (typeof data?.message === 'string') return data.message
  if (error.response) return `Request failed with status ${error.response.status}.`
  if (error.code === 'ECONNABORTED') return 'The request timed out. Please try again.'
  return 'Unable to reach the server. Check your connection and try again.'
}

export default apiClient

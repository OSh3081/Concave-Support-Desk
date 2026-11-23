const ACCESS_TOKEN_KEY = 'concave_access_token'

export type UserRole = 'MEMBER' | 'SUPPORT_AGENT' | 'SUPPORT_HEAD'

export type AuthUser = {
  id: number
  name: string
  email: string
  role: UserRole
}

export type LoginResponse = {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  expires_at: string
  user: AuthUser
}

/** Reads the assessment session token for API requests. */
export function getAccessToken(): string | null {
  return typeof window === 'undefined' ? null : window.localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function storeAccessToken(token: string): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token)
}

export function clearAccessToken(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY)
}

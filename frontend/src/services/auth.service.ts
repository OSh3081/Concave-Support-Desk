const ACCESS_TOKEN_KEY = 'concave_access_token'

/** Reads the token for API requests; login and token lifecycle are implemented in Stage E.2. */
export function getAccessToken(): string | null {
  return typeof window === 'undefined' ? null : window.localStorage.getItem(ACCESS_TOKEN_KEY)
}

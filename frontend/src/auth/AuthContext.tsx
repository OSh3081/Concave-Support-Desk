import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import apiClient from '../services/apiClient'
import { clearAccessToken, getAccessToken, storeAccessToken, type AuthUser, type LoginResponse } from '../services/auth.service'

type AuthContextValue = {
  user: AuthUser | null
  role: AuthUser['role'] | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<AuthUser>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const logout = useCallback(() => {
    clearAccessToken()
    setUser(null)
  }, [])

  useEffect(() => {
    const onSessionExpired = () => setUser(null)
    window.addEventListener('concave:session-expired', onSessionExpired)
    const token = getAccessToken()
    if (!token) {
      setIsLoading(false)
      return () => window.removeEventListener('concave:session-expired', onSessionExpired)
    }

    let active = true
    apiClient.get<AuthUser>('/auth/me')
      .then(({ data }) => {
        if (active) setUser(data)
      })
      .catch(() => {
        // A 401 clears the token centrally. Keep it through temporary network outages.
        if (active) setUser(null)
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })

    return () => {
      active = false
      window.removeEventListener('concave:session-expired', onSessionExpired)
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', { email, password })
    // Trust the backend role as the authority; the client only accepts known dashboard roles.
    if (!['MEMBER', 'SUPPORT_AGENT', 'SUPPORT_HEAD'].includes(data.user.role)) {
      throw new Error('This account does not have access to the support desk.')
    }
    storeAccessToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const value = useMemo(() => ({ user, role: user?.role ?? null, isLoading, login, logout }), [user, isLoading, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}

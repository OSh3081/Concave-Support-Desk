import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { dashboardForRole } from '../../auth/routing'
import type { UserRole } from '../../services/auth.service'

export default function ProtectedRoute({ role, children }: { role: UserRole; children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) {
    return <main className="grid min-h-screen place-items-center" aria-label="Restoring session"><p className="text-sm text-slate-600">Restoring your session…</p></main>
  }
  if (!user) return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />
  if (user.role !== role) return <Navigate to={dashboardForRole[user.role]} replace />
  return <>{children}</>
}

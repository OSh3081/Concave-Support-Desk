import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/common/ProtectedRoute'
import { useAuth } from './auth/AuthContext'
import { dashboardForRole } from './auth/routing'
import AdminPage from './pages/AdminPage'
import LoginPage from './pages/LoginPage'
import MemberPage from './pages/MemberPage'
import NotFoundPage from './pages/NotFoundPage'
import SupportPage from './pages/SupportPage'
import CreateTicketPage from './pages/CreateTicketPage'
import TicketDetailPage from './pages/TicketDetailPage'

export default function App() {
  const { user, isLoading } = useAuth()
  const root = isLoading ? <main className="grid min-h-screen place-items-center"><p className="text-sm text-slate-600">Restoring your session…</p></main> : <Navigate replace to={user ? dashboardForRole[user.role] : '/login'} />
  return (
    <Routes>
      <Route path="/" element={root} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/member" element={<ProtectedRoute role="MEMBER"><MemberPage /></ProtectedRoute>} />
      <Route path="/member/tickets/new" element={<ProtectedRoute role="MEMBER"><CreateTicketPage /></ProtectedRoute>} />
      <Route path="/member/tickets/:ticketId" element={<ProtectedRoute role="MEMBER"><TicketDetailPage /></ProtectedRoute>} />
      <Route path="/support" element={<ProtectedRoute role="SUPPORT_AGENT"><SupportPage /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute role="SUPPORT_HEAD"><AdminPage /></ProtectedRoute>} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

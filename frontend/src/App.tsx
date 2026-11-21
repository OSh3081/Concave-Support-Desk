import { Navigate, Route, Routes } from 'react-router-dom'
import AdminPage from './pages/AdminPage'
import LoginPage from './pages/LoginPage'
import MemberPage from './pages/MemberPage'
import NotFoundPage from './pages/NotFoundPage'
import SupportPage from './pages/SupportPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate replace to="/login" />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/member" element={<MemberPage />} />
      <Route path="/support" element={<SupportPage />} />
      <Route path="/admin" element={<AdminPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

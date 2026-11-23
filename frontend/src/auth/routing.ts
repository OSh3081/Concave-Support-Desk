import type { UserRole } from '../services/auth.service'

export const dashboardForRole: Record<UserRole, string> = {
  MEMBER: '/member',
  SUPPORT_AGENT: '/support',
  SUPPORT_HEAD: '/admin',
}

export function rolesForPath(path: string): UserRole[] | null {
  const pathname = path.split(/[?#]/, 1)[0]
  if (pathname === '/member' || pathname.startsWith('/member/')) return ['MEMBER']
  if (pathname === '/support' || pathname.startsWith('/support/')) return ['SUPPORT_AGENT', 'SUPPORT_HEAD']
  if (pathname === '/admin' || pathname.startsWith('/admin/')) return ['SUPPORT_HEAD']
  return null
}

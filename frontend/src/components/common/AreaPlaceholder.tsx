import { useAuth } from '../../auth/AuthContext'
import { Link } from 'react-router-dom'

type AreaPlaceholderProps = {
  eyebrow: string
  title: string
  description: string
  action?: { href: string; label: string }
}

export default function AreaPlaceholder({ eyebrow, title, description, action }: AreaPlaceholderProps) {
  const { user, logout } = useAuth()
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8 sm:px-6 sm:py-12">
      <section className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-10">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-800 sm:text-sm">
          Concave Insights · Support Desk
        </p>
        <p className="mt-8 text-sm font-medium text-slate-500">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{title}</h1>
        <p className="mt-4 leading-7 text-slate-600">{description}</p>
        {action && <Link to={action.href} className="mt-6 inline-flex min-h-11 items-center rounded-lg bg-emerald-800 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700">{action.label}</Link>}
        <div className="mt-8 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-slate-500"><p className="font-medium text-slate-700">Signed in as {user?.name}</p><p className="mt-1">Role: {user?.role}</p></div>
          <button type="button" onClick={logout} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Sign out</button>
        </div>
      </section>
    </main>
  )
}

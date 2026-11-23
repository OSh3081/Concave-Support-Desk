import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { dashboardForRole, rolesForPath } from '../auth/routing'
import { getApiErrorMessage } from '../services/apiClient'

type LoginLocationState = { from?: string }

export default function LoginPage() {
  const { user, isLoading, login } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [emailTouched, setEmailTouched] = useState(false)

  if (isLoading) return <main className="grid min-h-screen place-items-center"><p className="text-sm text-slate-600">Restoring your session…</p></main>
  if (user) return <Navigate replace to={dashboardForRole[user.role]} />

  const normalizedEmail = email.trim()
  const emailInvalid = emailTouched && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setEmailTouched(true)
    setError('')
    setSuccess(false)
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      setError('Enter a valid email address.')
      return
    }
    if (password.length === 0) {
      setError('Enter your password.')
      return
    }

    setIsSubmitting(true)
    try {
      const signedInUser = await login(normalizedEmail, password)
      setSuccess(true)
      const destination = (location.state as LoginLocationState | null)?.from
      const roles = rolesForPath(destination ?? '')
      navigate(roles?.includes(signedInUser.role) ? destination! : dashboardForRole[signedInUser.role], { replace: true })
    } catch (requestError) {
      const message = getApiErrorMessage(requestError)
      setError(message.toLowerCase().includes('invalid email or password')
        ? 'That email and password do not match. Check your details and try again.'
        : message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f7f6] lg:grid lg:grid-cols-[1.05fr_0.95fr]">
      <section className="relative hidden overflow-hidden bg-[#173b36] px-12 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-20">
        <div className="absolute -right-24 top-24 size-96 rounded-full border border-white/10" />
        <div className="absolute -right-10 top-40 size-72 rounded-full border border-white/10" />
        <Link to="/" className="relative flex items-center gap-3 text-sm font-semibold"><span className="grid size-10 place-items-center rounded-xl bg-white/10">C</span>Concave <span className="font-normal text-white/65">Support Desk</span></Link>
        <div className="relative max-w-xl pb-16">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#a8cec0]">Support that moves things forward</p>
          <h1 className="mt-6 text-5xl font-semibold leading-[1.08] tracking-tight xl:text-6xl">A clearer way to get help.</h1>
          <p className="mt-6 max-w-lg text-lg leading-8 text-white/70">Sign in to connect with the right team and keep every conversation moving.</p>
          <div className="mt-12 flex items-center gap-3 text-sm text-white/70"><span className="grid size-9 place-items-center rounded-full bg-white/10 text-[#b7ddcf]">✦</span> Thoughtful support, built around you.</div>
        </div>
        <p className="relative text-xs text-white/45">© Concave Insights · Support Desk</p>
      </section>

      <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-md">
          <Link to="/" className="mb-12 flex items-center gap-3 text-sm font-semibold text-slate-900 lg:hidden"><span className="grid size-10 place-items-center rounded-xl bg-[#173b36] text-white">C</span>Concave <span className="font-normal text-slate-500">Support Desk</span></Link>
          <div className="mb-8">
            <p className="text-sm font-semibold text-[#28705c]">Welcome back</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Sign in to your account</h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">Use your work email and password to continue.</p>
          </div>

          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            <div>
              <label htmlFor="email" className="mb-2 block text-sm font-medium text-slate-800">Email address</label>
              <input id="email" name="email" type="email" autoComplete="username" inputMode="email" required value={email} onChange={(event) => setEmail(event.target.value)} onBlur={() => setEmailTouched(true)} aria-invalid={emailInvalid} aria-describedby={emailInvalid ? 'email-error' : undefined} className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-950 shadow-sm transition placeholder:text-slate-400 hover:border-slate-400 focus:border-[#347b66] focus:outline-none focus:ring-4 focus:ring-[#347b66]/10" placeholder="you@company.com" />
              {emailInvalid && <p id="email-error" className="mt-1.5 text-xs text-red-700">Enter a valid email address.</p>}
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between"><label htmlFor="password" className="block text-sm font-medium text-slate-800">Password</label></div>
              <div className="relative">
                <input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 pr-20 text-sm text-slate-950 shadow-sm transition placeholder:text-slate-400 hover:border-slate-400 focus:border-[#347b66] focus:outline-none focus:ring-4 focus:ring-[#347b66]/10" placeholder="Enter your password" />
                <button type="button" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? 'Hide password' : 'Show password'} className="absolute inset-y-0 right-3 my-auto rounded-md px-2 text-xs font-semibold text-slate-600 hover:text-slate-950">{showPassword ? 'Hide' : 'Show'}</button>
              </div>
            </div>
            {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-800">{error}{error.toLowerCase().includes('server') || error.toLowerCase().includes('reach') || error.toLowerCase().includes('timed out') ? <span className="mt-1 block text-xs text-red-700">The sign-in service may be offline. Check that the backend is running, then try again.</span> : null}</div>}
            {success && <p role="status" className="text-sm text-emerald-800">Signed in successfully. Opening your workspace…</p>}
            <button type="submit" disabled={isSubmitting} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#173b36] px-4 py-3.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#205248] focus-visible:outline-offset-4 disabled:cursor-wait disabled:opacity-70">{isSubmitting && <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden="true" />}{isSubmitting ? 'Signing in…' : 'Sign in'}</button>
          </form>

          <div className="mt-8 border-t border-slate-200 pt-5 text-center text-xs leading-5 text-slate-500">Need access? Contact your Concave Support Desk administrator.</div>
          <p className="mt-10 text-center text-xs text-slate-400 lg:hidden">Concave Insights · Support Desk</p>
        </div>
      </section>
    </main>
  )
}

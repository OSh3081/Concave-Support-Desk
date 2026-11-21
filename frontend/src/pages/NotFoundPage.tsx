import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <section className="max-w-lg text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-emerald-800">404 · Page not found</p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">That page isn’t here.</h1>
        <p className="mt-3 text-slate-600">Check the address or return to the sign-in page.</p>
        <Link
          className="mt-7 inline-flex rounded-lg bg-emerald-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-800"
          to="/login"
        >
          Go to sign in
        </Link>
      </section>
    </main>
  )
}

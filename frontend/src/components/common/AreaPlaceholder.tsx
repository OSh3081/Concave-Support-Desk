type AreaPlaceholderProps = {
  eyebrow: string
  title: string
  description: string
}

export default function AreaPlaceholder({ eyebrow, title, description }: AreaPlaceholderProps) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8 sm:px-6 sm:py-12">
      <section className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-10">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-800 sm:text-sm">
          Concave Insights · Support Desk
        </p>
        <p className="mt-8 text-sm font-medium text-slate-500">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{title}</h1>
        <p className="mt-4 leading-7 text-slate-600">{description}</p>
        <p className="mt-8 border-t border-slate-100 pt-5 text-sm text-slate-500">
          Frontend foundation · Stage E.1
        </p>
      </section>
    </main>
  )
}

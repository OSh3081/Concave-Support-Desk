export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col bg-[#f7f8fa]">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6 lg:px-10">
        <a className="flex items-center gap-3" href="/" aria-label="Concave Support Desk home">
          <span className="grid size-10 place-items-center rounded-xl bg-[#173b36] text-sm font-bold text-white">C</span>
          <span className="text-sm font-semibold tracking-tight text-slate-900">Concave <span className="font-normal text-slate-500">Support Desk</span></span>
        </a>
        <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600">Development preview</span>
      </header>

      <section className="mx-auto grid w-full max-w-6xl flex-1 items-center gap-12 px-6 pb-16 pt-8 lg:grid-cols-[1.15fr_0.85fr] lg:px-10 lg:py-20">
        <div>
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-[#d8e8e3] bg-[#edf5f2] px-3.5 py-2 text-xs font-semibold text-[#275c50]">
            <span className="size-2 rounded-full bg-[#3d9078]" />
            A calmer way to support every customer
          </div>
          <h1 className="max-w-2xl text-5xl font-semibold leading-[1.08] tracking-[-0.045em] text-slate-950 sm:text-6xl">Concave Support Desk</h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-slate-600">A workspace for the people who help things move forward. We’re building a clear, reliable place to manage support requests from first question to resolution.</p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <span className="rounded-lg bg-[#173b36] px-5 py-3 text-sm font-medium text-white">Under development</span>
            <span className="text-sm text-slate-500">The support workspace is coming together.</span>
          </div>
        </div>

        <div className="relative mx-auto w-full max-w-md">
          <div className="absolute -inset-5 rounded-[2rem] bg-[#e7efed] blur-2xl" />
          <div className="relative rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_24px_70px_-36px_rgba(23,59,54,0.38)] sm:p-7">
            <div className="flex items-center justify-between border-b border-slate-100 pb-5">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">Workspace preview</p>
                <h2 className="mt-1 text-base font-semibold text-slate-900">Support overview</h2>
              </div>
              <span className="rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs text-slate-500">Preview</span>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <PreviewCard label="Open requests" value="—" />
              <PreviewCard label="Resolved today" value="—" />
            </div>
            <div className="mt-4 rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-5">
              <div className="flex items-center gap-3">
                <div className="grid size-9 place-items-center rounded-lg bg-[#e5efec] text-[#275c50]" aria-hidden="true">✦</div>
                <div>
                  <p className="text-sm font-medium text-slate-800">Your support queue will live here</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">Ticket tools and team workflows are being built.</p>
                </div>
              </div>
            </div>
            <div className="mt-5 flex items-center gap-2 text-xs text-slate-400">
              <span className="size-1.5 rounded-full bg-amber-400" />
              Early build · More updates soon
            </div>
          </div>
          <p className="mt-5 text-center text-xs text-slate-400">A first look at Concave Support Desk</p>
        </div>
      </section>

      <footer className="mx-auto flex w-full max-w-6xl flex-col gap-2 border-t border-slate-200/80 px-6 py-5 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between lg:px-10">
        <span>Concave Insights · Support Desk</span>
        <span>Built with care for better support experiences</span>
      </footer>
    </main>
  )
}

function PreviewCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-800">{value}</p>
    </div>
  )
}

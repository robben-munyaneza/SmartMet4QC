import clsx from 'clsx'
import { Bell, Cpu, LayoutDashboard, Menu, WifiOff, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { HEALTH } from '../lib/meta'
import { useAlerts, useBatches } from '../lib/queries'
import { SOLID_TONE } from '../lib/tones'

const HEALTH_ORDER = ['problem', 'watch', 'ready', 'good', 'no-data', 'closed']

function NavItem({ to, icon, children, end }: { to: string; icon: ReactNode; children: ReactNode; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => clsx(
        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
        isActive ? 'bg-surface-2 text-ink' : 'text-ink-2 hover:bg-surface-2 hover:text-ink',
      )}
    >
      {icon}
      {children}
    </NavLink>
  )
}

function Sidebar() {
  const batches = useBatches()
  const alerts = useAlerts('open')
  const active = (batches.data ?? [])
    .filter((b) => b.status === 'active')
    .sort((a, b) => HEALTH_ORDER.indexOf(a.health) - HEALTH_ORDER.indexOf(b.health) || a.code.localeCompare(b.code))
  const problems = (alerts.data ?? []).filter((a) => a.severity !== 'info').length
  const offline = batches.isError

  return (
    <div className="flex h-full flex-col gap-1 px-3 py-5">
      <NavLink to="/" className="mb-5 flex items-center gap-3 px-2">
        <span className="grid size-9 place-items-center rounded-[10px] bg-accent text-sm font-extrabold text-white">QC</span>
        <span>
          <span className="block font-bold leading-tight">SmartMet4QC</span>
          <span className="block text-xs text-muted">Fermentation quality</span>
        </span>
      </NavLink>

      <nav className="grid gap-0.5" aria-label="Main">
        <NavItem to="/" end icon={<LayoutDashboard size={18} aria-hidden />}>Overview</NavItem>
        <NavItem to="/alerts" icon={<Bell size={18} aria-hidden />}>
          Alerts
          {problems > 0 && (
            <span className="ml-auto rounded-full bg-crit px-2 text-xs font-bold text-white" aria-label={`${problems} open problems`}>
              {problems}
            </span>
          )}
        </NavItem>
        <NavItem to="/devices" icon={<Cpu size={18} aria-hidden />}>Devices</NavItem>
      </nav>

      <div className="mt-6 mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-muted">Active batches</div>
      <nav className="grid gap-0.5 overflow-y-auto" aria-label="Active batches">
        {active.length === 0 && <span className="px-3 text-sm text-muted">No active batches</span>}
        {active.map((b) => (
          <NavItem key={b.code} to={`/batches/${encodeURIComponent(b.code)}`}
            icon={<span className={clsx('size-2.5 rounded-full', SOLID_TONE[HEALTH[b.health].tone])} aria-hidden />}>
            <span className="truncate">{b.code}</span>
            <span className="ml-auto text-xs text-muted">{HEALTH[b.health].label}</span>
          </NavItem>
        ))}
      </nav>

      <div className="mt-auto px-3 pt-4 text-xs text-muted">
        {offline
          ? <span className="flex items-center gap-1.5 text-crit-ink"><WifiOff size={14} aria-hidden /> Server not reachable</span>
          : batches.dataUpdatedAt
            ? `Updated ${new Date(batches.dataUpdatedAt).toLocaleTimeString()} · every 10 s`
            : 'Connecting…'}
      </div>
    </div>
  )
}

export function Layout() {
  // The phone menu remembers the page it was opened on, so it closes when you navigate.
  const { pathname } = useLocation()
  const [openOn, setOpenOn] = useState<string | null>(null)
  const open = openOn === pathname
  const setOpen = (value: boolean) => setOpenOn(value ? pathname : null)

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_minmax(0,1fr)]">
      <aside
        id="sidebar"
        className={clsx(
          'fixed inset-y-0 left-0 z-30 w-64 border-r border-line bg-sidebar transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <button className="absolute top-4 right-3 rounded-lg p-1.5 text-muted hover:bg-surface-2 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
          <X size={20} />
        </button>
        <Sidebar />
      </aside>
      {open && <div className="fixed inset-0 z-20 bg-black/40 lg:hidden" onClick={() => setOpen(false)} aria-hidden />}

      <div className="min-w-0">
        <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-line bg-page/90 px-4 py-3 backdrop-blur lg:hidden">
          <button className="rounded-lg border border-line p-2" onClick={() => setOpen(true)} aria-label="Open menu" aria-controls="sidebar" aria-expanded={open}>
            <Menu size={18} />
          </button>
          <span className="font-bold">SmartMet4QC</span>
        </div>
        <main className="mx-auto grid w-full max-w-[1280px] grid-cols-[minmax(0,1fr)] gap-5 px-4 pt-5 pb-12 sm:px-8 sm:pt-7">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end gap-3">
      <div className="min-w-0">
        <h1 className="flex flex-wrap items-center gap-3 text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="ml-auto flex flex-wrap gap-2">{actions}</div>}
    </header>
  )
}

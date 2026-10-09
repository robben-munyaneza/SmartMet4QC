import clsx from 'clsx'
import { CircleCheck } from 'lucide-react'
import { useState } from 'react'
import { AlertItem } from '../components/AlertItem'
import { PageHeader } from '../components/Layout'
import { Empty, Message } from '../components/ui'
import type { Alert } from '../lib/api'
import { ruleText } from '../lib/meta'
import { useAlerts } from '../lib/queries'

const RANK = { critical: 0, warning: 1, info: 2 }

const GROUPS = [
  { key: 'process', title: 'Needs action', hint: 'Problems with the batch itself' },
  { key: 'sensor', title: 'Sensor problems', hint: 'A value may be wrong; check the sensor' },
  { key: 'info', title: 'Information', hint: 'Good news and notes' },
] as const

export function AlertsPage() {
  const [view, setView] = useState<'open' | 'resolved'>('open')
  const alerts = useAlerts(view)
  const list = [...(alerts.data ?? [])].sort((a, b) => RANK[a.severity] - RANK[b.severity] || b.opened_at.localeCompare(a.opened_at))
  const grouped = (key: string) => list.filter((a: Alert) => ruleText(a.rule, a.measurement).group === key)

  return (
    <>
      <PageHeader
        title="Alerts"
        subtitle="Every alert explains what it means and what to do. Alerts close by themselves when the problem is gone."
        actions={
          <div className="inline-flex rounded-lg border border-line bg-surface p-0.5" role="group" aria-label="Show">
            {(['open', 'resolved'] as const).map((v) => (
              <button key={v} onClick={() => setView(v)} aria-pressed={view === v}
                className={clsx('rounded-md px-3.5 py-1.5 text-sm font-semibold', view === v ? 'bg-surface-2 text-ink' : 'text-muted hover:text-ink')}>
                {v === 'open' ? 'Open' : 'Resolved'}
              </button>
            ))}
          </div>
        }
      />

      {alerts.isError && <Message tone="error">{alerts.error.message}</Message>}
      {!alerts.isLoading && list.length === 0 && (
        <Empty>
          <span className="inline-flex items-center gap-2"><CircleCheck size={16} aria-hidden />
            {view === 'open' ? 'No open alerts. All batches are in the normal range.' : 'No resolved alerts yet.'}</span>
        </Empty>
      )}

      {GROUPS.map((g) => {
        const items = grouped(g.key)
        if (!items.length) return null
        return (
          <section key={g.key} className="grid gap-3">
            <div className="flex items-baseline gap-3">
              <h2 className="text-base font-semibold">{g.title}</h2>
              <span className="text-sm text-muted">{items.length} · {g.hint}</span>
            </div>
            {items.map((a) => <AlertItem key={a.batch_id + a.rule + a.measurement + a.opened_at} alert={a} showBatch />)}
          </section>
        )
      })}
    </>
  )
}

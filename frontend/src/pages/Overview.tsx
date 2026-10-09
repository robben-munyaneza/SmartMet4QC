import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Activity, CircleCheck, Cpu, Plus, TriangleAlert } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BatchCard } from '../components/BatchCard'
import { PageHeader } from '../components/Layout'
import { Button, Card, CardHeader, Chip, Empty, Field, IconBadge, Message, inputClass } from '../components/ui'
import { api, type BatchSummary } from '../lib/api'
import { formatDateTime } from '../lib/format'
import { HEALTH, ruleText, type Tone } from '../lib/meta'
import { useBatches, useDevices, useLimits } from '../lib/queries'

const ORDER = ['problem', 'watch', 'ready', 'good', 'no-data']

function headline(active: BatchSummary[]): { tone: Tone; title: string; text: string } {
  const problem = active.filter((b) => b.health === 'problem')
  const watch = active.filter((b) => b.health === 'watch')
  const ready = active.filter((b) => b.health === 'ready')
  const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 'es'}`
  const describe = (b: BatchSummary) =>
    `${b.code}: ${b.top_alert ? ruleText(b.top_alert.rule, b.top_alert.measurement).title : 'check it'}`

  if (!active.length) return { tone: 'neutral', title: 'No active batches', text: 'Start a batch below, or send readings from a device or the simulator.' }
  if (problem.length) return { tone: 'crit', title: `${plural(problem.length, 'batch')} need${problem.length === 1 ? 's' : ''} action now`, text: problem.map(describe).join(' · ') }
  if (watch.length) return { tone: 'warn', title: `${plural(watch.length, 'batch')} to keep an eye on`, text: watch.map(describe).join(' · ') }
  if (ready.length) return { tone: 'good', title: `${plural(ready.length, 'batch')} ready to finish`, text: `${ready.map((b) => b.code).join(', ')}: sugar is stable. Taste-check and mark finished.` }
  return { tone: 'good', title: 'All active batches look good', text: 'Every value is in the normal range. Nothing to do right now.' }
}

function Kpi({ icon, label, value, sub }: { icon: ReactNode; label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <Card className="p-4!">
      <div className="flex items-center gap-2 text-sm text-ink-2">{icon}{label}</div>
      <div className="mt-1 text-3xl font-bold tabular-nums">{value}</div>
      {sub && <div className="text-[13px] text-muted">{sub}</div>}
    </Card>
  )
}

function NewBatchForm() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [code, setCode] = useState('')
  const [notes, setNotes] = useState('')
  const create = useMutation({
    mutationFn: api.createBatch,
    onSuccess: (batch) => {
      queryClient.invalidateQueries({ queryKey: ['batches'] })
      navigate(`/batches/${encodeURIComponent(batch.code)}`)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate({ code: code.trim(), notes: notes.trim() || null })
  }
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
      <Field label="Batch code">
        <input className={inputClass} required maxLength={50} pattern="[A-Za-z0-9_\-]+" placeholder="BATCH-010"
          value={code} onChange={(e) => setCode(e.target.value)} />
      </Field>
      <Field label="Notes (optional)">
        <input className={`${inputClass} w-72`} maxLength={200} placeholder="e.g. 40 L, new banana supplier"
          value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      <Button variant="primary" type="submit" disabled={create.isPending}><Plus size={16} /> Start batch</Button>
      {create.isError && <div className="basis-full"><Message tone="error">{create.error.message}</Message></div>}
    </form>
  )
}

export function Overview() {
  const batches = useBatches()
  const devices = useDevices()
  const limits = useLimits()
  const [showForm, setShowForm] = useState(false)

  const all = batches.data ?? []
  const active = all.filter((b) => b.status === 'active').sort((a, b) => ORDER.indexOf(a.health) - ORDER.indexOf(b.health))
  const closed = all.filter((b) => b.status !== 'active')
  const attention = active.filter((b) => b.health === 'problem' || b.health === 'watch')
  const online = (devices.data ?? []).filter((d) => d.online).length
  const head = headline(active)

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle={new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
        actions={<Button variant="primary" onClick={() => setShowForm((v) => !v)}><Plus size={16} /> New batch</Button>}
      />

      {showForm && (
        <Card>
          <CardHeader title="Start a new batch" hint="Devices and hand-entered values can then be added to it." />
          <NewBatchForm />
        </Card>
      )}

      {batches.isError ? (
        <Message tone="error">{batches.error.message}</Message>
      ) : (
        <Card className="flex items-center gap-4">
          <IconBadge tone={head.tone} size={48} />
          <div className="min-w-0">
            <h2 className="text-xl font-bold">{batches.isLoading ? 'Loading…' : head.title}</h2>
            {!batches.isLoading && <p className="text-ink-2">{head.text}</p>}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi icon={<Activity size={16} aria-hidden />} label="Active batches" value={active.length} sub={`${all.length} in total`} />
        <Kpi icon={<TriangleAlert size={16} aria-hidden />} label="Need attention" value={attention.length}
          sub={`${active.filter((b) => b.health === 'problem').length} problem · ${active.filter((b) => b.health === 'watch').length} watch`} />
        <Kpi icon={<CircleCheck size={16} aria-hidden />} label="Ready to finish" value={active.filter((b) => b.health === 'ready').length} sub="sugar stable for a day" />
        <Kpi icon={<Cpu size={16} aria-hidden />} label="Devices online" value={`${online}/${devices.data?.length ?? 0}`}
          sub={<Link className="text-accent-ink hover:underline" to="/devices">Manage devices</Link>} />
      </div>

      <section className="grid gap-3">
        <h2 className="text-base font-semibold">Active batches</h2>
        {active.length === 0 && !batches.isLoading
          ? <Empty>No active batches. Use “New batch” to start one.</Empty>
          : (
            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {active.map((b) => <BatchCard key={b.code} batch={b} limits={limits.data} />)}
            </div>
          )}
      </section>

      {closed.length > 0 && (
        <Card>
          <CardHeader title="Finished and stopped batches" hint={`${closed.length}`} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-[13px] text-muted">
                <tr className="border-b border-line">
                  <th className="py-2 pr-4 font-medium">Batch</th>
                  <th className="py-2 pr-4 font-medium">Result</th>
                  <th className="py-2 pr-4 text-right font-medium">Readings</th>
                  <th className="py-2 font-medium">Last reading</th>
                </tr>
              </thead>
              <tbody>
                {closed.map((b) => (
                  <tr key={b.code} className="border-b border-line last:border-0">
                    <td className="py-2.5 pr-4"><Link className="font-semibold text-accent-ink hover:underline" to={`/batches/${encodeURIComponent(b.code)}`}>{b.code}</Link></td>
                    <td className="py-2.5 pr-4"><Chip tone={b.status === 'finished' ? 'good' : 'neutral'}>{b.status === 'finished' ? 'Finished' : 'Aborted'}</Chip></td>
                    <td className="py-2.5 pr-4 text-right tabular-nums">{b.readings}</td>
                    <td className="py-2.5 text-ink-2">{formatDateTime(b.last)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <p className="text-xs text-muted">
        Health: {Object.values(HEALTH).filter((h) => h.label !== 'Closed').map((h) => `${h.label} = ${h.description.toLowerCase()}`).join(' · ')}.
        Progress is estimated from the drop in sugar (Brix).
      </p>
    </>
  )
}

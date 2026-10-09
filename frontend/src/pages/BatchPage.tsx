import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowDown, ArrowRight, ArrowUp, CircleCheck, Flag, History, RotateCcw, Table2, XCircle } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertItem } from '../components/AlertItem'
import { BatchDevices } from '../components/BatchDevices'
import { PageHeader } from '../components/Layout'
import { ManualEntry } from '../components/ManualEntry'
import { MeasurementChart } from '../components/MeasurementChart'
import { Button, Card, CardHeader, Chip, Empty, IconBadge, Message, ProgressBar } from '../components/ui'
import { api, type Alert, type BatchDetail, type BatchStatus, type MeasurementKey, type Reading } from '../lib/api'
import { batchStart, dayNumber, formatAgo, formatDateTime, trend } from '../lib/format'
import { HEALTH, MEASUREMENTS, MEASUREMENT_ORDER, SEVERITY, formatValue, outOfRange, ruleText, type Tone } from '../lib/meta'
import { useAlerts, useBatch, useReadings } from '../lib/queries'

const SEVERITY_RANK = { critical: 0, warning: 1, info: 2 }

function StatusActions({ batch }: { batch: BatchDetail }) {
  const queryClient = useQueryClient()
  const update = useMutation({
    mutationFn: (status: BatchStatus) => api.updateBatch(batch.code, { status }),
    onSuccess: () => queryClient.invalidateQueries(),
  })
  const change = (status: BatchStatus, question: string) => {
    if (window.confirm(question)) update.mutate(status)
  }
  if (batch.status !== 'active') {
    return <Button onClick={() => change('active', 'Reopen this batch?')}><RotateCcw size={16} /> Reopen</Button>
  }
  return (
    <>
      <Button variant={batch.health === 'ready' ? 'primary' : 'secondary'} onClick={() => change('finished', 'Mark this batch as finished?')}>
        <Flag size={16} /> Mark finished
      </Button>
      <Button variant="danger" onClick={() => change('aborted', 'Abort this batch? Use this when the batch is thrown away.')}>
        <XCircle size={16} /> Abort
      </Button>
    </>
  )
}

/** "What is happening": plain sentences, most serious first. */
function Summary({ batch, alerts }: { batch: BatchDetail; alerts: Alert[] }) {
  const open = alerts.filter((a) => a.status === 'open')
    .sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity])
  const problems = open.filter((a) => a.severity !== 'info')
  const brix = batch.latest.brix

  const rows: { tone: Tone; title: ReactNode; text?: ReactNode }[] = problems.map((a) => {
    const text = ruleText(a.rule, a.measurement)
    return { tone: SEVERITY[a.severity].tone, title: text.title, text: <><b>What to do:</b> {text.todo}</> }
  })
  if (batch.status !== 'active') {
    rows.unshift({ tone: 'neutral', title: `This batch is ${batch.status}.`, text: batch.ended_at ? `Closed ${formatDateTime(batch.ended_at)}.` : undefined })
  } else if (!problems.length) {
    rows.push(batch.health === 'ready'
      ? { tone: 'good', title: 'Fermentation looks finished', text: <><b>What to do:</b> taste-check the batch and mark it finished.</> }
      : batch.health === 'no-data'
        ? { tone: 'neutral', title: 'Waiting for the first reading', text: 'Assign a device below or enter values by hand.' }
        : { tone: 'good', title: 'Everything is in the normal range', text: 'Nothing to do right now.' })
  }

  return (
    <Card>
      <CardHeader title="What is happening" />
      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <ul className="grid gap-4">
          {rows.map((r, i) => (
            <li key={i} className="flex gap-3">
              <IconBadge tone={r.tone} size={30} />
              <div>
                <div className="font-semibold">{r.title}</div>
                {r.text && <div className="text-sm text-ink-2">{r.text}</div>}
              </div>
            </li>
          ))}
        </ul>
        <div className="grid content-start gap-2 rounded-lg bg-surface-2 p-4">
          <div className="flex justify-between text-sm">
            <span className="text-ink-2">Fermentation progress</span>
            <span className="font-semibold">{batch.progress === null ? '–' : `${Math.round(batch.progress * 100)}%`}</span>
          </div>
          {batch.progress !== null && <ProgressBar value={batch.progress} done={batch.health === 'ready'} />}
          <p className="text-[13px] text-muted">
            {batch.brix_start !== null && brix
              ? `Sugar went from ${batch.brix_start.toFixed(1)} to ${brix.value.toFixed(1)} °Bx. Nearly done below ${batch.limits.brix_done}.`
              : 'Enter a Brix value to follow progress.'}
          </p>
          {batch.ethanol_estimate !== null && !batch.latest.ethanol_percent && (
            <p className="text-[13px] text-muted">Estimated alcohol: ≈ {batch.ethanol_estimate.toFixed(1)} % (rough; confirm in a lab)</p>
          )}
        </div>
      </div>
    </Card>
  )
}

function TrendText({ readings, measurement }: { readings: Reading[]; measurement: MeasurementKey }) {
  const t = trend(readings, measurement)
  if (!t) return null
  const meta = MEASUREMENTS[measurement]
  const steady = Math.abs(t.delta) < meta.noise
  const Icon = steady ? ArrowRight : t.delta > 0 ? ArrowUp : ArrowDown
  return (
    <span className="flex items-center gap-1">
      <Icon size={14} aria-hidden />
      {steady ? `Steady over the last ${t.hours} h` : `${t.delta > 0 ? '+' : '−'}${Math.abs(t.delta).toFixed(meta.digits)} ${meta.unit} in ${t.hours} h`}
    </span>
  )
}

function ValueTile({ batch, measurement, readings, sensorIssue }: {
  batch: BatchDetail; measurement: MeasurementKey; readings: Reading[]; sensorIssue?: string
}) {
  const meta = MEASUREMENTS[measurement]
  const latest = batch.latest[measurement]
  const off = latest ? outOfRange(measurement, latest.value, batch.limits) : null
  let status: { tone: Tone; label: string }
  if (!latest) status = { tone: 'neutral', label: 'No value yet' }
  else if (sensorIssue) status = { tone: 'warn', label: 'Check sensor' }
  else if (off) status = { tone: 'crit', label: off === 'high' ? 'Too high' : 'Too low' }
  else if (measurement === 'brix') status = latest.value <= batch.limits.brix_done ? { tone: 'good', label: 'Nearly done' } : { tone: 'info', label: 'Fermenting' }
  else status = { tone: 'good', label: 'OK' }

  return (
    <Card className={clsx('grid gap-2 p-4!', status.tone === 'crit' && 'border-crit/50')}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-ink-2">{meta.label}</span>
        <Chip tone={status.tone}>{status.label}</Chip>
      </div>
      <div className="text-4xl font-bold tabular-nums">
        {formatValue(measurement, latest?.value)}
        <span className="ml-1 text-base font-medium text-muted">{meta.unit}</span>
      </div>
      <div className="grid gap-0.5 text-[13px] text-muted">
        <span>{meta.rangeText(batch.limits)}</span>
        <span className="text-ink-2"><TrendText readings={readings} measurement={measurement} /></span>
        {sensorIssue && <span className="text-warn-ink">{sensorIssue}</span>}
        {latest && <span>Measured {formatAgo(latest.measured_at)}</span>}
      </div>
    </Card>
  )
}

function ReadingsTable({ readings, measurements }: { readings: Reading[]; measurements: MeasurementKey[] }) {
  const rows = readings.slice(-300).reverse()
  return (
    <div className="max-h-[420px] overflow-auto rounded-lg border border-line">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-surface-2 text-left text-[13px] text-muted">
          <tr>
            <th className="px-3 py-2 font-medium">Time</th>
            <th className="px-3 py-2 font-medium">Source</th>
            {measurements.map((m) => <th key={m} className="px-3 py-2 text-right font-medium">{MEASUREMENTS[m].label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.measured_at + r.source} className="border-t border-line">
              <td className="whitespace-nowrap px-3 py-1.5">{formatDateTime(r.measured_at)}</td>
              <td className="px-3 py-1.5 text-ink-2">{r.source === 'manual' ? 'by hand' : r.source}</td>
              {measurements.map((m) => <td key={m} className="px-3 py-1.5 text-right tabular-nums">{formatValue(m, r[m])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function BatchPage() {
  const code = decodeURIComponent(useParams().code ?? '')
  const batch = useBatch(code)
  const readings = useReadings(code)
  const alerts = useAlerts('all', code)
  const [showTable, setShowTable] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  if (batch.isError) {
    const notFound = batch.error.message.includes('not found')
    return (
      <>
        <PageHeader title={code} />
        <Message tone="error">{notFound ? 'There is no batch with this code.' : batch.error.message}</Message>
        <Link className="text-accent-ink hover:underline" to="/">← Back to the overview</Link>
      </>
    )
  }
  if (!batch.data) return <PageHeader title={code} subtitle="Loading…" />

  const b = batch.data
  const rows = readings.data ?? []
  const allAlerts = alerts.data ?? []
  const start = batchStart(b.started_at, rows[0]?.measured_at) ?? 0
  const day = dayNumber(start, rows[rows.length - 1]?.measured_at)
  const withData = MEASUREMENT_ORDER.filter((m) => rows.some((r) => r[m] !== null))
  const tiles = MEASUREMENT_ORDER.filter((m) => ['temperature_c', 'ph', 'brix'].includes(m) || b.latest[m])
  const sensorIssues: Partial<Record<string, string>> = {}
  for (const a of allAlerts) {
    if (a.status === 'open' && a.rule.startsWith('sensor_')) sensorIssues[a.measurement] = ruleText(a.rule, a.measurement).title
  }
  const resolved = allAlerts.filter((a) => a.status === 'resolved')
  const health = HEALTH[b.health]

  return (
    <>
      <PageHeader
        title={<>{b.code} <Chip tone={health.tone}>{health.label}</Chip></>}
        subtitle={[
          day ? `Day ${day} of fermentation` : null,
          b.started_at ? `started ${formatDateTime(b.started_at)}` : null,
          b.product,
          b.notes,
        ].filter(Boolean).join(' · ')}
        actions={<StatusActions batch={b} />}
      />

      <Summary batch={b} alerts={allAlerts} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {tiles.map((m) => (
          <ValueTile key={m} batch={b} measurement={m} readings={rows} sensorIssue={sensorIssues[m]} />
        ))}
      </div>

      <Card>
        <CardHeader
          title="Charts"
          hint="The shaded band is the normal range. Hover a chart for exact values."
          right={withData.length > 0 && (
            <Button variant="ghost" onClick={() => setShowTable((v) => !v)}>
              <Table2 size={16} /> {showTable ? 'Show charts' : 'Show as table'}
            </Button>
          )}
        />
        {withData.length === 0
          ? <Empty>No readings yet.</Empty>
          : showTable
            ? <ReadingsTable readings={rows} measurements={withData} />
            : (
              <div className="grid gap-8 xl:grid-cols-2">
                {withData.map((m) => <MeasurementChart key={m} measurement={m} readings={rows} start={start} limits={b.limits} />)}
              </div>
            )}
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader title="Enter values by hand" hint="From a refractometer, pH meter or thermometer" />
          <ManualEntry batchCode={b.code} disabled={b.status !== 'active'} />
        </Card>
        <Card>
          <CardHeader title="Devices measuring this batch" />
          <BatchDevices batchCode={b.code} active={b.status === 'active'} />
        </Card>
      </div>

      <Card>
        <CardHeader
          title={<span className="flex items-center gap-2"><History size={18} aria-hidden /> Alert history</span>}
          hint={`${resolved.length} resolved`}
          right={resolved.length > 0 && (
            <Button variant="ghost" onClick={() => setShowHistory((v) => !v)}>{showHistory ? 'Hide' : 'Show'}</Button>
          )}
        />
        {resolved.length === 0
          ? <p className="flex items-center gap-2 text-sm text-muted"><CircleCheck size={16} aria-hidden /> No resolved alerts.</p>
          : showHistory && <div className="grid gap-3">{resolved.map((a) => <AlertItem key={a.rule + a.measurement + a.opened_at} alert={a} />)}</div>}
      </Card>
    </>
  )
}

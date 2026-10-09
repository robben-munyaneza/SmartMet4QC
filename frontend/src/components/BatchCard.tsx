import clsx from 'clsx'
import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { BatchSummary, Limits, MeasurementKey } from '../lib/api'
import { batchStart, dayNumber, formatAgo } from '../lib/format'
import { HEALTH, MEASUREMENTS, formatValue, outOfRange, ruleText } from '../lib/meta'
import { TONE_ICON } from '../lib/tones'
import { Chip, ProgressBar } from './ui'

const MINIS: MeasurementKey[] = ['temperature_c', 'ph', 'brix']

const BORDER = { crit: 'border-l-crit', warn: 'border-l-warn', good: 'border-l-good', info: 'border-l-accent', neutral: 'border-l-line' }

export function BatchCard({ batch, limits }: { batch: BatchSummary; limits?: Limits }) {
  const health = HEALTH[batch.health]
  const day = dayNumber(batchStart(batch.started_at, batch.first), batch.last)
  const issue = batch.top_alert && batch.top_alert.severity !== 'info'
    ? ruleText(batch.top_alert.rule, batch.top_alert.measurement).title
    : null
  const IssueIcon = TONE_ICON[issue ? health.tone : 'good']

  return (
    <Link
      to={`/batches/${encodeURIComponent(batch.code)}`}
      className={clsx(
        'group grid gap-4 rounded-xl border border-l-4 border-line bg-surface p-5 transition hover:border-accent hover:shadow-md',
        BORDER[health.tone],
      )}
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0">
          <div className="truncate text-lg font-bold">{batch.code}</div>
          <div className="text-sm text-muted">
            {day ? `Day ${day} of fermentation` : 'Not started'} · {formatAgo(batch.last)}
          </div>
        </div>
        <span className="ml-auto"><Chip tone={health.tone}>{health.label}</Chip></span>
      </div>

      <div className="grid gap-1.5">
        <div className="flex justify-between text-sm">
          <span className="text-ink-2">Fermentation progress</span>
          <span className="font-semibold">
            {batch.progress === null ? '–' : `${Math.round(batch.progress * 100)}%`}
          </span>
        </div>
        {batch.progress === null
          ? <p className="text-xs text-muted">Enter a Brix value to follow progress</p>
          : <ProgressBar value={batch.progress} done={batch.health === 'ready'} />}
      </div>

      <div className="grid grid-cols-3 gap-2">
        {MINIS.map((key) => {
          const latest = batch.latest[key]
          const off = latest && limits ? outOfRange(key, latest.value, limits) : null
          return (
            <div key={key} className="rounded-lg bg-surface-2 px-3 py-2">
              <div className="truncate text-xs text-muted">{MEASUREMENTS[key].label}</div>
              <div className={clsx('flex items-baseline gap-1 font-semibold tabular-nums', off && 'text-crit-ink')}>
                {formatValue(key, latest?.value)}
                <span className="text-xs font-normal text-muted">{MEASUREMENTS[key].unit}</span>
                {off && <span className="text-xs font-bold" aria-label={off === 'high' ? 'too high' : 'too low'}>{off === 'high' ? '▲' : '▼'}</span>}
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex items-center gap-2 border-t border-line pt-3 text-sm">
        <IssueIcon size={16} className={issue ? (health.tone === 'crit' ? 'text-crit-ink' : 'text-warn-ink') : 'text-good-ink'} aria-hidden />
        <span className={clsx('truncate', issue ? 'font-medium' : 'text-ink-2')}>
          {issue ?? (batch.health === 'ready' ? 'Sugar is stable: ready to taste-check' : batch.health === 'no-data' ? 'Waiting for the first reading' : 'All values in the normal range')}
        </span>
        <ChevronRight size={16} className="ml-auto shrink-0 text-muted transition group-hover:translate-x-0.5" aria-hidden />
      </div>
    </Link>
  )
}

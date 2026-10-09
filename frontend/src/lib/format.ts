import type { MeasurementKey, Reading } from './api'

const HOUR = 3_600_000

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '–'
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/** "5 min ago" for recent times, otherwise the date. Simulated batches can have future times. */
export function formatAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return 'never'
  const diff = now - Date.parse(iso)
  if (diff < 0 || diff > 48 * HOUR) return formatDateTime(iso)
  const minutes = Math.round(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(diff / HOUR)
  return hours < 24 ? `${hours} h ago` : 'yesterday'
}

/** Start of the batch clock: the batch start or the first reading, whichever is earlier. */
export function batchStart(startedAt: string | null, first: string | null | undefined): number | null {
  const times = [startedAt, first].filter((t): t is string => !!t).map(Date.parse)
  return times.length ? Math.min(...times) : null
}

/** Day of fermentation (day 1 = the first 24 hours). */
export function dayNumber(start: number | null, iso: string | null | undefined): number | null {
  if (start === null || !iso) return null
  return Math.max(1, Math.floor((Date.parse(iso) - start) / (24 * HOUR)) + 1)
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.floor(sorted.length / 2)]
}

/**
 * Change over the last `hours`: median of the latest 3 values minus the median of
 * the 3 values around `hours` earlier. Medians keep one bad value from showing a trend.
 */
export function trend(readings: Reading[], key: MeasurementKey, hours = 6): { delta: number; hours: number } | null {
  const points = readings
    .filter((r) => r[key] !== null)
    .map((r) => ({ t: Date.parse(r.measured_at), v: r[key] as number }))
  if (points.length < 2) return null
  const last = points[points.length - 1].t
  let i = points.length - 1
  while (i >= 0 && points[i].t > last - hours * HOUR) i--
  if (i < 0) return null
  const recent = points.slice(-3).map((p) => p.v)
  const before = points.slice(Math.max(0, i - 1), i + 2).map((p) => p.v)
  return { delta: median(recent) - median(before), hours: Math.round((last - points[i].t) / HOUR) }
}

export function toLocalInput(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

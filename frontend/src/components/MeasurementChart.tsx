import {
  CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { Limits, MeasurementKey, Reading } from '../lib/api'
import { formatDateTime } from '../lib/format'
import { MEASUREMENTS, formatValue } from '../lib/meta'
import { useCssColors } from '../lib/useCssColors'

const COLORS = ['series-1', 'series-2', 'grid', 'axis', 'muted', 'ink', 'ink-2', 'surface', 'line', 'band', 'good'] as const
const DAY = 86_400_000

interface Point {
  x: number          // days since the batch started
  t: number          // time (ms)
  sensor?: number
  manual?: number
}

function TooltipBox({ active, payload, measurement }: {
  active?: boolean
  payload?: ReadonlyArray<{ payload?: unknown }>
  measurement: MeasurementKey
}) {
  const p = payload?.[0]?.payload as Point | undefined
  if (!active || !p) return null
  const meta = MEASUREMENTS[measurement]
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-sm shadow-lg">
      <div className="font-semibold">{formatDateTime(new Date(p.t).toISOString())}</div>
      <div className="text-xs text-muted">day {Math.floor(p.x) + 1} of fermentation</div>
      {p.sensor !== undefined && <div className="mt-1 tabular-nums">Sensor: <b>{formatValue(measurement, p.sensor)}</b> {meta.unit}</div>}
      {p.manual !== undefined && <div className="mt-1 tabular-nums">By hand: <b>{formatValue(measurement, p.manual)}</b> {meta.unit}</div>}
    </div>
  )
}

export function MeasurementChart({ measurement, readings, start, limits }: {
  measurement: MeasurementKey
  readings: Reading[]
  start: number
  limits: Limits
}) {
  const c = useCssColors(COLORS)
  const meta = MEASUREMENTS[measurement]
  const points: Point[] = readings
    .filter((r) => r[measurement] !== null)
    .map((r) => {
      const t = Date.parse(r.measured_at)
      const value = r[measurement] as number
      return { x: (t - start) / DAY, t, ...(r.source === 'manual' ? { manual: value } : { sensor: value }) }
    })
  const hasSensor = points.some((p) => p.sensor !== undefined)
  const hasManual = points.some((p) => p.manual !== undefined)
  const range = meta.range(limits)
  // An open-ended range ("above 3.5") is shaded up to the data's edge, not the other way.
  const values = points.map((p) => (p.sensor ?? p.manual) as number)
  const band = range && {
    y1: range.min ?? Math.min(...values, range.max ?? 0),
    y2: range.max ?? Math.max(...values, range.min ?? 0),
  }
  const lastDay = Math.max(1, Math.ceil(points.length ? points[points.length - 1].x : 1))
  const ticks = Array.from({ length: lastDay + 1 }, (_, i) => i)

  return (
    <figure className="grid gap-2">
      <figcaption className="flex flex-wrap items-baseline gap-x-3">
        <h3 className="font-semibold">{meta.label}{meta.unit && <span className="font-normal text-muted"> ({meta.unit})</span>}</h3>
        <span className="text-[13px] text-muted">{meta.rangeText(limits)}</span>
      </figcaption>
      <div className="flex flex-wrap gap-4 text-[13px] text-ink-2" aria-hidden>
        {hasSensor && <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded" style={{ background: c['series-1'] }} />Sensor</span>}
        {hasManual && <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full" style={{ background: c['series-2'] }} />Entered by hand</span>}
        {range && <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm" style={{ background: c.band, outline: `1px solid ${c.good}55` }} />Normal range</span>}
        {measurement === 'brix' && <span className="flex items-center gap-1.5"><span className="w-4 border-t-2 border-dashed" style={{ borderColor: c.good }} />Nearly done</span>}
      </div>
      <div className="h-60" role="img" aria-label={`${meta.label} over the batch`}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
            <CartesianGrid stroke={c.grid} vertical={false} />
            {band && (
              <ReferenceArea y1={band.y1} y2={band.y2} fill={c.band} fillOpacity={1} stroke="none" ifOverflow="extendDomain" />
            )}
            {measurement === 'brix' && (
              <ReferenceLine y={limits.brix_done} stroke={c.good} strokeDasharray="5 4" ifOverflow="extendDomain" />
            )}
            <XAxis dataKey="x" type="number" domain={[0, lastDay]} ticks={ticks} tickFormatter={(d: number) => `day ${d + 1}`}
              stroke={c.axis} tick={{ fill: c.muted, fontSize: 12 }} tickLine={false} axisLine={{ stroke: c.grid }} />
            <YAxis domain={['auto', 'auto']} stroke={c.axis} tick={{ fill: c.muted, fontSize: 12 }} tickLine={false} axisLine={false}
              width={48} tickFormatter={(v: number) => formatValue(measurement, v)} />
            <Tooltip content={(props) => <TooltipBox {...props} measurement={measurement} />}
              cursor={{ stroke: c.axis, strokeWidth: 1 }} isAnimationActive={false} />
            {hasSensor && (
              <Line dataKey="sensor" type="monotone" stroke={c['series-1']} strokeWidth={2} dot={false} connectNulls
                activeDot={{ r: 4, stroke: c.surface, strokeWidth: 2 }} isAnimationActive={false} />
            )}
            {hasManual && (
              <Scatter dataKey="manual" fill={c['series-2']} stroke={c.surface} strokeWidth={2} isAnimationActive={false} />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}

// Types and calls for the SmartMet4QC API (smartmet_api/main.py).

export type Severity = 'critical' | 'warning' | 'info'
export type Health = 'problem' | 'watch' | 'ready' | 'good' | 'no-data' | 'closed'
export type BatchStatus = 'active' | 'finished' | 'aborted'
export type MeasurementKey = 'temperature_c' | 'ph' | 'brix' | 'turbidity_ntu' | 'ethanol_percent'

export interface LatestValue {
  value: number
  measured_at: string
}

export interface TopAlert {
  rule: string
  measurement: string
  severity: Severity
  message: string
}

interface HealthFields {
  health: Health
  open_alerts: Record<Severity, number>
  top_alert: TopAlert | null
  brix_start: number | null
  progress: number | null
}

export interface BatchSummary extends HealthFields {
  code: string
  status: BatchStatus
  readings: number
  first: string | null
  last: string | null
  started_at: string | null
  latest: Partial<Record<MeasurementKey, LatestValue>>
}

export interface Limits {
  temp_max_c: number
  temp_min_c: number
  ph_min: number
  turbidity_max_ntu: number
  brix_done: number
}

export interface BatchDetail extends HealthFields {
  code: string
  product: string
  status: BatchStatus
  started_at: string | null
  ended_at: string | null
  notes: string | null
  latest: Partial<Record<MeasurementKey, LatestValue>>
  ethanol_estimate: number | null
  limits: Limits
}

export type Reading = {
  measured_at: string
  received_at: string
  source: 'simulated' | 'device' | 'manual'
  simulation: Record<string, unknown> | null
} & Record<MeasurementKey, number | null>

export interface Alert {
  batch_id: string
  rule: string
  measurement: string
  severity: Severity
  status: 'open' | 'resolved'
  message: string
  value: number | null
  opened_at: string
  last_seen_at: string
  resolved_at: string | null
}

export interface Device {
  name: string
  active: boolean
  batch_id: string | null
  last_seen_at: string | null
  online: boolean
}

export interface StoreResult {
  stored: boolean
  duplicate: boolean
  batch_id: string
  new_alerts: Alert[]
}

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown, message: string) {
    super(message)
    this.status = status
    this.body = body
  }
}

function detailText(body: unknown): string | null {
  if (!body || typeof body !== 'object' || !('detail' in body)) return null
  const detail = (body as { detail: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => (d as { msg?: string }).msg ?? '').join('; ')
  return null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init })
  } catch {
    throw new ApiError(0, null, 'Cannot reach the SmartMet4QC server. Is it running?')
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(response.status, body, detailText(body) ?? `Server error (${response.status})`)
  }
  return body as T
}

const enc = encodeURIComponent
const json = (method: string, data: unknown): RequestInit => ({ method, body: JSON.stringify(data) })

export const api = {
  batches: () => request<BatchSummary[]>('/api/v1/batches'),
  batch: (code: string) => request<BatchDetail>(`/api/v1/batches/${enc(code)}`),
  readings: (code: string) => request<Reading[]>(`/api/v1/batches/${enc(code)}/readings?limit=10000`),
  alerts: (status: 'open' | 'resolved' | 'all', batch?: string) =>
    request<Alert[]>(`/api/v1/alerts?status=${status}&limit=1000${batch ? `&batch=${enc(batch)}` : ''}`),
  devices: () => request<Device[]>('/api/v1/devices'),
  limits: () => request<Limits>('/api/v1/limits'),

  createBatch: (data: { code: string; notes: string | null }) =>
    request<BatchDetail>('/api/v1/batches', json('POST', data)),
  updateBatch: (code: string, data: { status: BatchStatus }) =>
    request<BatchDetail>(`/api/v1/batches/${enc(code)}`, json('PATCH', data)),
  manualReading: (data: {
    batch_id: string
    timestamp: string
    measurements: Partial<Record<MeasurementKey, number>>
    confirm: boolean
  }) => request<StoreResult>('/api/v1/manual-readings', json('POST', data)),
  assignDevice: (name: string, batchCode: string | null) =>
    request<Device>(`/api/v1/devices/${enc(name)}`, json('PATCH', { batch_id: batchCode })),
}

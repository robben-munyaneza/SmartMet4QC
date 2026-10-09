import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError, api, type MeasurementKey, type StoreResult } from '../lib/api'
import { toLocalInput } from '../lib/format'
import { ruleText } from '../lib/meta'
import { Button, Field, Message, inputClass } from './ui'

interface FieldSpec { key: MeasurementKey; label: string; step: string; min: number; max?: number }

// Measured every day (the MVP's hand-entered Brix, and spot checks of pH and temperature).
const DAILY: FieldSpec[] = [
  { key: 'brix', label: 'Sugar (Brix, °Bx)', step: '0.1', min: 0, max: 100 },
  { key: 'ph', label: 'pH', step: '0.01', min: 0, max: 14 },
  { key: 'temperature_c', label: 'Temperature (°C)', step: '0.1', min: -50, max: 150 },
]
// Measured now and then, e.g. a lab result or a check at bottling. Optional.
const LAB: FieldSpec[] = [
  { key: 'ethanol_percent', label: 'Ethanol (% alcohol)', step: '0.1', min: 0, max: 100 },
  { key: 'turbidity_ntu', label: 'Turbidity (NTU)', step: '1', min: 0 },
]
const FIELDS = [...DAILY, ...LAB]

type Values = Record<MeasurementKey, string>
const EMPTY: Values = { brix: '', ph: '', temperature_c: '', ethanol_percent: '', turbidity_ntu: '' }

/** Values typed in from hand-held instruments. The server checks for typos first (HTTP 409). */
export function ManualEntry({ batchCode, disabled }: { batchCode: string; disabled?: boolean }) {
  const queryClient = useQueryClient()
  const [values, setValues] = useState<Values>(EMPTY)
  const [time, setTime] = useState(() => toLocalInput(new Date()))
  const [warnings, setWarnings] = useState<string[] | null>(null)
  const [result, setResult] = useState<StoreResult | null>(null)

  const save = useMutation({
    mutationFn: (confirm: boolean) => {
      const measurements: Partial<Record<MeasurementKey, number>> = {}
      for (const f of FIELDS) {
        const raw = values[f.key]
        if (raw !== '') measurements[f.key] = Number(raw)
      }
      return api.manualReading({ batch_id: batchCode, timestamp: new Date(time).toISOString(), measurements, confirm })
    },
    onMutate: () => { setWarnings(null); setResult(null) },
    onSuccess: (stored) => {
      setResult(stored)
      setValues(EMPTY)
      setTime(toLocalInput(new Date()))
      queryClient.invalidateQueries()
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setWarnings(((error.body as { warnings?: string[] }) ?? {}).warnings ?? [error.message])
      }
    },
  })

  const empty = Object.values(values).every((v) => v === '')
  const input = (f: FieldSpec) => (
    <Field key={f.key} label={f.label}>
      <input className={`${inputClass} w-40 tabular-nums`} type="number" step={f.step} min={f.min} max={f.max}
        value={values[f.key]} disabled={disabled}
        onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))} />
    </Field>
  )
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!empty) save.mutate(false)
  }

  return (
    <div>
      <form onSubmit={submit} className="grid gap-4">
        <div className="flex flex-wrap items-end gap-3">{DAILY.map(input)}</div>
        <div className="grid gap-2">
          <div className="text-[13px] text-muted">Lab or bottling values (optional), e.g. measured alcohol and clarity:</div>
          <div className="flex flex-wrap items-end gap-3">{LAB.map(input)}</div>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Measured at">
            <input className={inputClass} type="datetime-local" required value={time} disabled={disabled}
              onChange={(e) => setTime(e.target.value)} />
          </Field>
          <Button variant="primary" type="submit" disabled={disabled || empty || save.isPending}>
            <Save size={16} /> Save
          </Button>
        </div>
      </form>

      {warnings && (
        <Message tone="warn">
          <strong>Please check this value. It looks unusual:</strong>
          <ul className="my-2 list-disc pl-5">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          <div className="flex gap-2">
            <Button type="button" onClick={() => save.mutate(true)}>The value is correct, save it</Button>
            <Button type="button" variant="ghost" onClick={() => setWarnings(null)}>Let me correct it</Button>
          </div>
        </Message>
      )}
      {save.isError && !warnings && <Message tone="error">{save.error.message}</Message>}
      {result && (
        <Message tone="ok">
          {result.duplicate ? 'A value for this exact time was already saved.' : 'Saved.'}
          {result.new_alerts.length > 0 && (
            <ul className="mt-1 list-disc pl-5">
              {result.new_alerts.map((a) => <li key={a.rule + a.measurement}>New alert: {ruleText(a.rule, a.measurement).title}</li>)}
            </ul>
          )}
        </Message>
      )}
    </div>
  )
}

// Plain-language texts: what each measurement, health state and alert means.

import type { Health, Limits, MeasurementKey, Severity } from './api'

export type Tone = 'good' | 'warn' | 'crit' | 'info' | 'neutral'

interface MeasurementMeta {
  label: string
  unit: string
  digits: number
  /** changes smaller than this are noise, shown as "steady" */
  noise: number
  /** normal range used for status, tiles and the shaded chart band */
  range: (l: Limits) => { min?: number; max?: number } | null
  rangeText: (l: Limits) => string
}

export const MEASUREMENTS: Record<MeasurementKey, MeasurementMeta> = {
  temperature_c: {
    label: 'Temperature', unit: '°C', digits: 1, noise: 0.3,
    range: (l) => ({ min: l.temp_min_c, max: l.temp_max_c }),
    rangeText: (l) => `Normal ${l.temp_min_c}–${l.temp_max_c} °C`,
  },
  ph: {
    label: 'pH', unit: '', digits: 2, noise: 0.05,
    range: (l) => ({ min: l.ph_min }),
    rangeText: (l) => `Normal above ${l.ph_min}`,
  },
  brix: {
    label: 'Sugar (Brix)', unit: '°Bx', digits: 1, noise: 0.3,
    range: () => null,
    rangeText: (l) => `Falls while fermenting · below ${l.brix_done} = nearly done`,
  },
  turbidity_ntu: {
    label: 'Turbidity', unit: 'NTU', digits: 0, noise: 3,
    range: (l) => ({ min: 0, max: l.turbidity_max_ntu }),
    rangeText: (l) => `Normal below ${l.turbidity_max_ntu} NTU`,
  },
  ethanol_percent: {
    label: 'Ethanol', unit: '%', digits: 1, noise: 0.2,
    range: () => null,
    rangeText: () => 'Rises while fermenting',
  },
}

export const MEASUREMENT_ORDER: MeasurementKey[] = ['temperature_c', 'ph', 'brix', 'turbidity_ntu', 'ethanol_percent']

export function formatValue(key: MeasurementKey, value: number | null | undefined): string {
  if (value === null || value === undefined) return '–'
  return value.toFixed(MEASUREMENTS[key].digits)
}

/** 'high' | 'low' when the value is outside the normal range, otherwise null */
export function outOfRange(key: MeasurementKey, value: number, limits: Limits): 'high' | 'low' | null {
  const range = MEASUREMENTS[key].range(limits)
  if (!range) return null
  if (range.max !== undefined && value > range.max) return 'high'
  if (range.min !== undefined && value < range.min) return 'low'
  return null
}

export const HEALTH: Record<Health, { label: string; tone: Tone; description: string }> = {
  problem: { label: 'Problem', tone: 'crit', description: 'Needs action now' },
  watch: { label: 'Watch', tone: 'warn', description: 'Something to check' },
  ready: { label: 'Ready', tone: 'good', description: 'Fermentation looks finished' },
  good: { label: 'Good', tone: 'good', description: 'Everything in the normal range' },
  'no-data': { label: 'Waiting', tone: 'neutral', description: 'No readings yet' },
  closed: { label: 'Closed', tone: 'neutral', description: 'Finished or stopped' },
}

export const SEVERITY: Record<Severity, { label: string; tone: Tone }> = {
  critical: { label: 'Critical', tone: 'crit' },
  warning: { label: 'Warning', tone: 'warn' },
  info: { label: 'Info', tone: 'info' },
}

interface RuleText {
  title: string
  explain: string
  todo: string
  group: 'process' | 'sensor' | 'info'
}

const PROCESS_RULES: Record<string, RuleText> = {
  temperature_high: {
    title: 'Batch is too warm',
    explain: 'The temperature has been above the normal range for more than one reading.',
    todo: 'Check the cooling and the room temperature. Move the batch somewhere cooler if needed.',
    group: 'process',
  },
  temperature_low: {
    title: 'Batch is too cold',
    explain: 'The temperature has been below the normal range. Fermentation slows down when it is too cold.',
    todo: 'Check the heating and the room temperature.',
    group: 'process',
  },
  ph_low: {
    title: 'pH is too low: possible souring',
    explain: 'The batch is more acidic than a healthy fermentation. This can mean souring or contamination.',
    todo: 'Check smell, taste and appearance. Review hygiene. If unsure, send a sample to the lab before bottling.',
    group: 'process',
  },
  turbidity_high: {
    title: 'Batch is unusually cloudy',
    explain: 'Turbidity is above the normal range, which can be a sign of contamination.',
    todo: 'Look at the batch and check for contamination.',
    group: 'process',
  },
  fermentation_stuck: {
    title: 'Fermentation has stopped',
    explain: 'The sugar level (Brix) has hardly gone down for a day, although the batch is not finished.',
    todo: 'Check the temperature and whether the batch is still bubbling. The yeast may need help.',
    group: 'process',
  },
  batch_finished: {
    title: 'Fermentation looks finished',
    explain: 'The sugar level has been stable for a day at a low value.',
    todo: 'Taste-check the batch. If it is ready, mark the batch as finished.',
    group: 'info',
  },
}

const SENSOR_RULES: Record<string, Omit<RuleText, 'title'> & { title: (m: string) => string }> = {
  sensor_spike: {
    title: (m) => `${m} jumped suddenly`,
    explain: 'One value is far from the values before it. This is usually a sensor or typing error, not a real change.',
    todo: 'Check the probe and its cable. If it was typed in by hand, check the value.',
    group: 'sensor',
  },
  sensor_stuck: {
    title: (m) => `${m} sensor may be frozen`,
    explain: 'The sensor has sent exactly the same value many times in a row.',
    todo: 'Check that the sensor is connected and working. Restart the device if needed.',
    group: 'sensor',
  },
  sensor_missing: {
    title: (m) => `No ${m.toLowerCase()} value`,
    explain: 'The sensor sent no value, although it worked before.',
    todo: 'Check the sensor cable and connection.',
    group: 'sensor',
  },
}

export function ruleText(rule: string, measurement: string): RuleText {
  const m = MEASUREMENTS[measurement as MeasurementKey]?.label ?? measurement
  const sensor = SENSOR_RULES[rule]
  if (sensor) return { ...sensor, title: sensor.title(m) }
  return PROCESS_RULES[rule] ?? { title: rule, explain: '', todo: '', group: 'process' }
}

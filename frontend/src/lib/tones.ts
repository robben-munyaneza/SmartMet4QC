import { CircleCheck, CircleDashed, Info, OctagonX, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { Tone } from './meta'

/** Icon per status tone: a status is always shown with an icon and a word, never colour alone. */
export const TONE_ICON: Record<Tone, LucideIcon> = {
  good: CircleCheck,
  warn: TriangleAlert,
  crit: OctagonX,
  info: Info,
  neutral: CircleDashed,
}

export const SOLID_TONE: Record<Tone, string> = {
  good: 'bg-good text-white',
  warn: 'bg-warn text-[#3b2a00]',
  crit: 'bg-crit text-white',
  info: 'bg-accent text-white',
  neutral: 'bg-muted text-white',
}

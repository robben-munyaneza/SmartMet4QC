import clsx from 'clsx'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { Tone } from '../lib/meta'
import { SOLID_TONE, TONE_ICON } from '../lib/tones'

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <section className={clsx('rounded-xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(0,0,0,0.04)]', className)}>
      {children}
    </section>
  )
}

export function CardHeader({ title, hint, right }: { title: ReactNode; hint?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <h2 className="text-base font-semibold">{title}</h2>
      {hint && <span className="text-sm text-muted">{hint}</span>}
      {right && <div className="ml-auto">{right}</div>}
    </div>
  )
}

const CHIP_TONE: Record<Tone, string> = {
  good: 'bg-good/15 text-good-ink',
  warn: 'bg-warn/20 text-warn-ink',
  crit: 'bg-crit/15 text-crit-ink',
  info: 'bg-accent/15 text-accent-ink',
  neutral: 'bg-surface-2 text-ink-2',
}

/** Status label: icon + word + tint. Never colour alone. */
export function Chip({ tone, children, icon = true }: { tone: Tone; children: ReactNode; icon?: boolean }) {
  const Icon = TONE_ICON[tone]
  return (
    <span className={clsx('inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[13px] font-semibold', CHIP_TONE[tone])}>
      {icon && <Icon size={14} strokeWidth={2.5} aria-hidden />}
      {children}
    </span>
  )
}

export function IconBadge({ tone, size = 40 }: { tone: Tone; size?: number }) {
  const Icon = TONE_ICON[tone]
  return (
    <span className={clsx('grid shrink-0 place-items-center rounded-full', SOLID_TONE[tone])} style={{ width: size, height: size }}>
      <Icon size={size * 0.5} strokeWidth={2.5} aria-hidden />
    </span>
  )
}

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'

export function Button({ variant = 'secondary', className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      {...props}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50',
        variant === 'primary' && 'bg-accent text-white hover:brightness-110',
        variant === 'secondary' && 'border border-line bg-surface hover:border-accent',
        variant === 'danger' && 'border border-line bg-surface text-crit-ink hover:border-crit',
        variant === 'ghost' && 'text-ink-2 hover:bg-surface-2',
        className,
      )}
    />
  )
}

export function ProgressBar({ value, done }: { value: number; done?: boolean }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className={clsx('h-full rounded-full', done ? 'bg-good' : 'bg-accent')} style={{ width: `${Math.max(2, value * 100)}%` }} />
    </div>
  )
}

export function Message({ tone, children }: { tone: 'ok' | 'error' | 'warn'; children: ReactNode }) {
  return (
    <div className={clsx('mt-3 rounded-lg px-4 py-3 text-sm',
      tone === 'ok' && 'bg-good/15 text-good-ink',
      tone === 'error' && 'bg-crit/15 text-crit-ink',
      tone === 'warn' && 'bg-warn/20 text-ink')}>
      {children}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-dashed border-line px-4 py-6 text-center text-sm text-muted">{children}</p>
}

export const inputClass =
  'rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none'

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1 text-[13px] font-medium text-ink-2">
      {label}
      {children}
    </label>
  )
}

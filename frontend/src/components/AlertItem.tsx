import clsx from 'clsx'
import { Link } from 'react-router-dom'
import type { Alert } from '../lib/api'
import { formatAgo, formatDateTime } from '../lib/format'
import { SEVERITY, ruleText } from '../lib/meta'
import { Chip, IconBadge } from './ui'

export function AlertItem({ alert, showBatch = false }: { alert: Alert; showBatch?: boolean }) {
  const text = ruleText(alert.rule, alert.measurement)
  const severity = SEVERITY[alert.severity]
  const resolved = alert.status === 'resolved'

  return (
    <article className={clsx('flex gap-4 rounded-xl border border-line bg-surface p-4', resolved && 'opacity-75')}>
      <IconBadge tone={resolved ? 'neutral' : severity.tone} size={36} />
      <div className="grid min-w-0 flex-1 gap-1.5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h3 className="font-semibold">{text.title}</h3>
          <Chip tone={resolved ? 'neutral' : severity.tone} icon={false}>{resolved ? 'Resolved' : severity.label}</Chip>
        </div>
        <p className="text-sm text-muted">
          {showBatch && (
            <>
              <Link className="font-medium text-accent-ink hover:underline" to={`/batches/${encodeURIComponent(alert.batch_id)}`}>
                {alert.batch_id}
              </Link>
              {' · '}
            </>
          )}
          <span title={formatDateTime(alert.opened_at)}>
            {resolved
              ? `${formatDateTime(alert.opened_at)} → resolved ${formatDateTime(alert.resolved_at)}`
              : `since ${formatAgo(alert.opened_at)}`}
          </span>
          {' · '}
          <span>{alert.message}</span>
        </p>
        {!resolved && text.explain && <p className="text-sm text-ink-2">{text.explain}</p>}
        {!resolved && text.todo && (
          <p className="text-sm"><span className="font-semibold">What to do: </span>{text.todo}</p>
        )}
      </div>
    </article>
  )
}

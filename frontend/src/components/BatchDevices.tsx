import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Cpu, Link2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { formatAgo } from '../lib/format'
import { useDevices } from '../lib/queries'
import { Button, Chip, Empty, Message, inputClass } from './ui'

export function BatchDevices({ batchCode, active }: { batchCode: string; active: boolean }) {
  const queryClient = useQueryClient()
  const devices = useDevices()
  const [chosen, setChosen] = useState('')
  const assign = useMutation({
    mutationFn: ({ name, batch }: { name: string; batch: string | null }) => api.assignDevice(name, batch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['devices'] }),
  })

  const all = devices.data ?? []
  const mine = all.filter((d) => d.batch_id === batchCode)
  const others = all.filter((d) => d.active && d.batch_id !== batchCode)
  const selected = others.some((d) => d.name === chosen) ? chosen : others[0]?.name ?? ''

  return (
    <div className="grid gap-3">
      {mine.length === 0
        ? <Empty>No device is measuring this batch. Values can still be entered by hand.</Empty>
        : mine.map((d) => (
          <div key={d.name} className="flex flex-wrap items-center gap-3 rounded-lg bg-surface-2 px-4 py-3">
            <Cpu size={18} className="text-muted" aria-hidden />
            <span className="font-semibold">{d.name}</span>
            <Chip tone={d.online ? 'good' : 'warn'}>{d.online ? 'Online' : 'Offline'}</Chip>
            <span className="text-sm text-muted">last contact {formatAgo(d.last_seen_at)}</span>
            <Button variant="ghost" className="ml-auto" onClick={() => {
              if (window.confirm(`Stop ${d.name} from measuring this batch?`)) assign.mutate({ name: d.name, batch: null })
            }}>Stop measuring</Button>
          </div>
        ))}

      {active && others.length > 0 && (
        <div className="flex flex-wrap items-end gap-3">
          <select className={inputClass} value={selected} onChange={(e) => setChosen(e.target.value)} aria-label="Device">
            {others.map((d) => (
              <option key={d.name} value={d.name}>{d.name}{d.batch_id ? ` (now on ${d.batch_id})` : ''}</option>
            ))}
          </select>
          <Button onClick={() => assign.mutate({ name: selected, batch: batchCode })} disabled={!selected || assign.isPending}>
            <Link2 size={16} /> Measure this batch
          </Button>
        </div>
      )}
      {assign.isError && <Message tone="error">{assign.error.message}</Message>}
    </div>
  )
}

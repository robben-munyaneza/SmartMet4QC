import { Cpu, KeyRound, Link2, Terminal } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/Layout'
import { Card, CardHeader, Chip, Empty, Message } from '../components/ui'
import { formatAgo, formatDateTime } from '../lib/format'
import { useDevices } from '../lib/queries'

function Step({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-2 text-ink-2">{icon}</span>
      <div><div className="font-semibold">{title}</div><div className="text-sm text-ink-2">{children}</div></div>
    </li>
  )
}

const code = 'rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[13px]'

export function DevicesPage() {
  const devices = useDevices()
  const list = devices.data ?? []

  return (
    <>
      <PageHeader title="Devices" subtitle="ESP32 sensor boxes that send temperature and pH automatically. A device is online when it sent something in the last 5 minutes." />
      {devices.isError && <Message tone="error">{devices.error.message}</Message>}

      <Card>
        <CardHeader title="All devices" hint={`${list.filter((d) => d.online).length} of ${list.length} online`} />
        {list.length === 0 && !devices.isLoading
          ? <Empty>No devices yet. See “Add a device” below.</Empty>
          : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-[13px] text-muted">
                  <tr className="border-b border-line">
                    <th className="py-2 pr-4 font-medium">Device</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 pr-4 font-medium">Measures batch</th>
                    <th className="py-2 font-medium">Last contact</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((d) => (
                    <tr key={d.name} className="border-b border-line last:border-0">
                      <td className="py-3 pr-4"><span className="flex items-center gap-2 font-semibold"><Cpu size={16} className="text-muted" aria-hidden />{d.name}</span></td>
                      <td className="py-3 pr-4">
                        {!d.active ? <Chip tone="neutral">Key revoked</Chip> : <Chip tone={d.online ? 'good' : 'warn'}>{d.online ? 'Online' : 'Offline'}</Chip>}
                      </td>
                      <td className="py-3 pr-4">
                        {d.batch_id
                          ? <Link className="font-medium text-accent-ink hover:underline" to={`/batches/${encodeURIComponent(d.batch_id)}`}>{d.batch_id}</Link>
                          : <span className="text-muted">none: readings are refused</span>}
                      </td>
                      <td className="py-3 text-ink-2" title={formatDateTime(d.last_seen_at)}>{formatAgo(d.last_seen_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>

      <Card>
        <CardHeader title="Add a device" hint="Full guide: docs/HARDWARE.md" />
        <ol className="grid gap-4">
          <Step icon={<Terminal size={16} />} title="Create it in a terminal">
            Run <code className={code}>python -m smartmet_db device add tank-1</code>. It prints the device key once.
          </Step>
          <Step icon={<KeyRound size={16} />} title="Put the key on the device">
            Copy the key into <code className={code}>config.h</code> of the ESP32 firmware, or test without hardware:
            {' '}<code className={code}>python simulator.py --device --api-key KEY --http</code>
          </Step>
          <Step icon={<Link2 size={16} />} title="Choose its batch">
            Open a batch and click “Measure this batch”. Until then the device's readings are refused.
          </Step>
        </ol>
      </Card>
    </>
  )
}

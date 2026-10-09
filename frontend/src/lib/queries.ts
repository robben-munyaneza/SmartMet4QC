import { useQuery } from '@tanstack/react-query'
import { api } from './api'

// Everything refreshes by itself every 10 seconds (see main.tsx).

export const useBatches = () => useQuery({ queryKey: ['batches'], queryFn: api.batches })

export const useBatch = (code: string) => useQuery({ queryKey: ['batch', code], queryFn: () => api.batch(code) })

export const useReadings = (code: string) =>
  useQuery({ queryKey: ['readings', code], queryFn: () => api.readings(code) })

export const useAlerts = (status: 'open' | 'resolved' | 'all', batch?: string) =>
  useQuery({ queryKey: ['alerts', status, batch ?? null], queryFn: () => api.alerts(status, batch) })

export const useDevices = () => useQuery({ queryKey: ['devices'], queryFn: api.devices })

export const useLimits = () => useQuery({ queryKey: ['limits'], queryFn: api.limits, staleTime: Infinity, refetchInterval: false })

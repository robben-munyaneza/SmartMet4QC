import { Link, Route, Routes } from 'react-router-dom'
import { Layout, PageHeader } from './components/Layout'
import { AlertsPage } from './pages/AlertsPage'
import { BatchPage } from './pages/BatchPage'
import { DevicesPage } from './pages/DevicesPage'
import { Overview } from './pages/Overview'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="batches/:code" element={<BatchPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="devices" element={<DevicesPage />} />
        <Route path="*" element={
          <PageHeader title="Page not found" subtitle={<Link className="text-accent-ink hover:underline" to="/">Back to the overview</Link>} />
        } />
      </Route>
    </Routes>
  )
}

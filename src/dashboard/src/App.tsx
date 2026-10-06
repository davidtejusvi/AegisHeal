import { Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { DashboardPage } from './pages/DashboardPage';
import { AnomaliesPage } from './pages/AnomaliesPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { ServicesPage } from './pages/ServicesPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="anomalies" element={<AnomaliesPage />} />
        <Route path="incidents" element={<IncidentsPage />} />
        <Route path="services" element={<ServicesPage />} />
      </Route>
    </Routes>
  );
}

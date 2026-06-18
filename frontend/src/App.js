import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MiningDataProvider } from './context/MiningDataContext';
import Layout from './components/Layout';
import BlockFoundOverlay from './components/BlockFoundOverlay';
import Dashboard from './pages/Dashboard';
import Hardware from './pages/Hardware';
import Pool from './pages/Pool';
import NetworkCoin from './pages/NetworkCoin';
import Profitability from './pages/Profitability';
import BlockDiscovery from './pages/BlockDiscovery';
import History from './pages/History';
import Alerts from './pages/Alerts';
import Settings from './pages/Settings';

export default function App() {
  return (
    <MiningDataProvider>
      <BrowserRouter>
        <BlockFoundOverlay />
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="hardware" element={<Hardware />} />
            <Route path="pool" element={<Pool />} />
            <Route path="network" element={<NetworkCoin />} />
            <Route path="profitability" element={<Profitability />} />
            <Route path="blocks" element={<BlockDiscovery />} />
            <Route path="history" element={<History />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </MiningDataProvider>
  );
}

import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useMiningData } from '../context/MiningDataContext';
import { StatusDot } from './UIPrimitives';
import { coinColor } from '../utils/format';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '⬡' },
  { to: '/hardware', label: 'Hardware', icon: '◧' },
  { to: '/pool', label: 'Pool', icon: '◎' },
  { to: '/network', label: 'Network & Coin', icon: '⛓' },
  { to: '/profitability', label: 'Profitability', icon: '◈' },
  { to: '/blocks', label: 'Block Discovery', icon: '▦' },
  { to: '/history', label: 'History', icon: '∿' },
  { to: '/alerts', label: 'Alerts', icon: '▲' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
];

export default function Layout() {
  const { stats, connected } = useMiningData();
  const coin = stats?.coin || 'XMR';
  const running = stats?.running;

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#0a0d12', color: '#e8eaf0' }}>
      <aside style={{
        width: '230px', flexShrink: 0, background: '#0d1015',
        borderRight: '1px solid #1e2530', display: 'flex', flexDirection: 'column',
        position: 'sticky', top: 0, height: '100vh',
      }}>
        <div style={{ padding: '22px 20px 18px 20px', borderBottom: '1px solid #1e2530' }}>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 800, fontSize: '15px', letterSpacing: '0.02em' }}>
            ISFCR<span style={{ color: '#00e676' }}>::</span>MINER
          </div>
          <div style={{ fontSize: '10px', color: '#5a6478', marginTop: '4px', letterSpacing: '0.05em' }}>MINING CONSOLE</div>
        </div>

        <div style={{ padding: '14px 20px', borderBottom: '1px solid #1e2530' }}>
          <div style={{ display: 'flex', alignItems: 'center', fontSize: '12px', marginBottom: '6px' }}>
            <StatusDot active={connected} />
            <span style={{ color: connected ? '#00e676' : '#5a6478' }}>{connected ? 'Backend online' : 'Backend offline'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', fontSize: '12px' }}>
            <StatusDot active={running} color={coinColor(coin)} />
            <span style={{ color: running ? coinColor(coin) : '#5a6478' }}>
              {running ? `Mining ${coin}` : 'Miner stopped'}
            </span>
          </div>
        </div>

        <nav style={{ flex: 1, padding: '14px 10px', overflowY: 'auto' }}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '9px 12px', borderRadius: '7px', marginBottom: '2px',
                fontSize: '13px', textDecoration: 'none',
                color: isActive ? '#e8eaf0' : '#8b95a8',
                background: isActive ? '#1a2128' : 'transparent',
                borderLeft: isActive ? '2px solid #00e676' : '2px solid transparent',
                transition: 'all 0.15s ease',
              })}
            >
              <span style={{ fontSize: '13px', width: '16px', textAlign: 'center', opacity: 0.8 }}>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div style={{ padding: '14px 20px', borderTop: '1px solid #1e2530', fontSize: '10px', color: '#3d4555' }}>
          v2.0 · pool data refreshes live
        </div>
      </aside>

      <main style={{ flex: 1, minWidth: 0 }}>
        <Outlet />
      </main>
    </div>
  );
}

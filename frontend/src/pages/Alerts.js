import React from 'react';
import { useMiningData } from '../context/MiningDataContext';
import { Card, EmptyState } from '../components/UIPrimitives';

export default function Alerts() {
  const { stats, errors } = useMiningData();
  if (!stats) return <div style={{ padding: 40, color: '#5a6478' }}>Connecting…</div>;

  const gpu = stats.gpu || {};
  const cpu = stats.cpu || {};
  const xmrig = stats.xmrig || {};
  const pool = stats.pool || {};

  const checks = [
    { label: 'High GPU temperature', triggered: gpu.warning, detail: `${gpu.temp}°C (threshold 82°C)` },
    { label: 'High CPU temperature', triggered: cpu.temp > 85, detail: `${cpu.temp}°C (threshold 85°C)` },
    { label: 'Hashrate is zero while running', triggered: stats.running && (xmrig.hashrate_1m || 0) === 0, detail: 'Waiting for pool connection' },
    { label: 'Miner crashed / stopped unexpectedly', triggered: !stats.running && stats.pid === null && errors.some(e => e.includes('stopped')), detail: '' },
    { label: 'Pool disconnected', triggered: stats.running && !xmrig.connected, detail: pool.error || '' },
    { label: 'Excessive rejected shares', triggered: (xmrig.rejected_shares || 0) > (xmrig.accepted_shares || 0) * 0.05 && (xmrig.accepted_shares || 0) > 20, detail: `${xmrig.rejected_shares || 0} rejected` },
    { label: 'Fan failure (0% under load)', triggered: gpu.fan_speed === 0 && gpu.gpu_util > 50, detail: '' },
  ];

  const active = checks.filter((c) => c.triggered);

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '32px 32px 60px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: 800, margin: '0 0 24px' }}>Alerts &amp; Health</h1>

      <Card title={`Active Alerts (${active.length})`}>
        {active.length === 0 ? (
          <EmptyState message="All clear — no active alerts." />
        ) : (
          active.map((a, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: '10px', padding: '10px 0',
              borderBottom: i < active.length - 1 ? '1px solid #181d25' : 'none',
            }}>
              <span style={{ color: '#ff1744', fontSize: 14 }}>⚠</span>
              <div>
                <div style={{ fontSize: 13, color: '#ffcdd2' }}>{a.label}</div>
                {a.detail && <div style={{ fontSize: 12, color: '#5a6478', marginTop: 2 }}>{a.detail}</div>}
              </div>
            </div>
          ))
        )}
      </Card>

      <div style={{ marginTop: 16 }}>
        <Card title="All Monitored Conditions">
          {checks.map((c, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', padding: '8px 0',
              borderBottom: i < checks.length - 1 ? '1px solid #181d25' : 'none', fontSize: 13,
            }}>
              <span style={{ color: '#8b95a8' }}>{c.label}</span>
              <span style={{ color: c.triggered ? '#ff1744' : '#00e676', fontFamily: 'JetBrains Mono, monospace' }}>
                {c.triggered ? 'TRIGGERED' : 'OK'}
              </span>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}

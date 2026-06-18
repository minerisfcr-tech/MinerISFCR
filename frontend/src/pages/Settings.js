import React from 'react';
import { useMiningData } from '../context/MiningDataContext';
import { Card } from '../components/UIPrimitives';
import { coinColor } from '../utils/format';

export default function Settings() {
  const { stats, actionPending, startMining } = useMiningData();
  if (!stats) return <div style={{ padding: 40, color: '#5a6478' }}>Connecting…</div>;

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '32px 32px 60px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: 800, margin: '0 0 24px' }}>Settings</h1>

      <Card title="Coin Selection">
        <div style={{ fontSize: 13, color: '#8b95a8', marginBottom: 14 }}>
          Wallet addresses are read from each coin's config file in <code>configs/</code> — change
          a wallet by editing that file directly, then restart the backend.
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {(stats.available_coins || []).map((c) => (
            <button
              key={c.key}
              onClick={() => startMining(c.key).catch(() => {})}
              disabled={actionPending}
              style={{
                padding: '12px 16px', borderRadius: 8, cursor: 'pointer',
                border: `1.5px solid ${stats.coin === c.key ? coinColor(c.key) : '#1e2530'}`,
                background: stats.coin === c.key ? `${coinColor(c.key)}15` : '#0d1015',
                color: stats.coin === c.key ? coinColor(c.key) : '#8b95a8',
                fontFamily: 'JetBrains Mono, monospace', textAlign: 'left', minWidth: 140,
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 14 }}>{c.key}</div>
              <div style={{ fontSize: 11, marginTop: 4 }}>{c.algo}</div>
              <div style={{ fontSize: 11, marginTop: 2, opacity: 0.7 }}>via {c.pool_provider}</div>
            </button>
          ))}
        </div>
      </Card>

      <div style={{ marginTop: 16 }}>
        <Card title="Active Configuration">
          <Row k="Coin" v={stats.coin} />
          <Row k="Algorithm" v={stats.algo} />
          <Row k="Pool Provider" v={(stats.available_coins || []).find(c => c.key === stats.coin)?.pool_provider} />
          <Row k="Wallet" v={stats.wallet} />
        </Card>
      </div>
    </div>
  );
}

const Row = ({ k, v }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #181d25', fontSize: '13px' }}>
    <span style={{ color: '#8b95a8' }}>{k}</span>
    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: '#e8eaf0', wordBreak: 'break-all', textAlign: 'right', maxWidth: '70%' }}>{v}</span>
  </div>
);

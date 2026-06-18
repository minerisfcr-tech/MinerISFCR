import React from 'react';
import { useMiningData } from '../context/MiningDataContext';
import { Card, ErrorBanner } from '../components/UIPrimitives';
import { fmt_hash } from '../utils/format';

export default function Profitability() {
  const { stats, errors } = useMiningData();
  if (!stats) return <div style={{ padding: 40, color: '#5a6478' }}>Connecting…</div>;
  const gpu = stats.gpu || {};
  const xmrig = stats.xmrig || {};

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '32px 32px 60px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: 800, margin: '0 0 24px' }}>Profitability</h1>
      <ErrorBanner errors={errors} />

      <Card title="Status">
        <div style={{ fontSize: '13px', color: '#8b95a8', lineHeight: 1.6, marginBottom: '16px' }}>
          Power-cost and net-profit calculations are intentionally not enabled yet — you asked to
          skip that math for now and show revenue only. Revenue itself needs a confirmed network
          hashrate + block reward per coin, which most of the pool APIs in use don't expose
          directly, so those numbers are left blank rather than guessed.
        </div>
        <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
          <Metric label="Hashrate" value={fmt_hash(xmrig.hashrate_1m)} />
          <Metric label="Power Draw" value={gpu.power_draw ? `${gpu.power_draw.toFixed(0)} W` : '—'} />
          <Metric label="Hashrate per Watt" value={gpu.power_draw && xmrig.hashrate_1m ? `${(xmrig.hashrate_1m / gpu.power_draw).toFixed(2)} H/W` : '—'} />
          <Metric label="Revenue / day" value="—" />
          <Metric label="Power Cost / day" value="—" />
          <Metric label="Net Profit / day" value="—" />
        </div>
      </Card>
    </div>
  );
}

const Metric = ({ label, value }) => (
  <div style={{ background: '#0d1015', border: '1px solid #1e2530', borderRadius: '8px', padding: '14px 16px', minWidth: '150px' }}>
    <div style={{ fontSize: '10px', color: '#5a6478', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>{label}</div>
    <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '18px', fontWeight: 700 }}>{value}</div>
  </div>
);

import React from 'react';
import { useMiningData } from '../context/MiningDataContext';
import { Card, ErrorBanner, Badge } from '../components/UIPrimitives';
import { fmt_hash, coinColor } from '../utils/format';

const Row = ({ k, v, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid #181d25', fontSize: '13px' }}>
    <span style={{ color: '#8b95a8' }}>{k}</span>
    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: color || '#e8eaf0' }}>{v}</span>
  </div>
);

export default function Pool() {
  const { stats, errors } = useMiningData();
  if (!stats) return <div style={{ padding: 40, color: '#5a6478' }}>Connecting…</div>;
  const pool = stats.pool || {};
  const xmrig = stats.xmrig || {};
  const color = coinColor(stats.coin);

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '32px 32px 60px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: 800, margin: '0 0 8px' }}>Pool Metrics</h1>
      <div style={{ fontSize: '13px', color: '#5a6478', marginBottom: '24px' }}>
        {stats.coin} via <span style={{ color }}>{pool.pool_name}</span> · wallet {stats.wallet ? `${stats.wallet.slice(0, 10)}…${stats.wallet.slice(-6)}` : '—'}
      </div>
      <ErrorBanner errors={errors} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
        <Card title="Miner Metrics">
          <Row k="Status" v={stats.running ? 'Running' : 'Stopped'} color={stats.running ? '#00e676' : '#5a6478'} />
          <Row k="Coin" v={stats.coin} />
          <Row k="Algorithm" v={stats.algo} />
          <Row k="Pool Connected" v={xmrig.connected ? 'Yes' : 'No'} color={xmrig.connected ? '#00e676' : '#ff1744'} />
          <Row k="Current Hashrate" v={fmt_hash(xmrig.hashrate_1m)} />
          <Row k="Avg 10m" v={fmt_hash(xmrig.hashrate_10m)} />
          <Row k="Avg 1h" v={fmt_hash(xmrig.hashrate_1h)} />
          <Row k="Miner Uptime" v={xmrig.uptime ? `${Math.floor(xmrig.uptime / 3600)}h ${Math.floor((xmrig.uptime % 3600) / 60)}m` : '—'} />
          <Row k="Accepted Shares" v={xmrig.accepted_shares ?? '—'} color="#00e676" />
          <Row k="Rejected Shares" v={xmrig.rejected_shares ?? '—'} color={xmrig.rejected_shares > 0 ? '#ff1744' : undefined} />
        </Card>

        <Card title="Pool-Side Metrics">
          {!pool.reachable && (
            <div style={{ marginBottom: 12 }}>
              <Badge color="#ff8a65" bg="#2a1410">{pool.error || 'Pool unreachable'}</Badge>
            </div>
          )}
          <Row k="Pool Hashrate" v={fmt_hash(pool.pool_hashrate)} />
          <Row k="Effective Hashrate" v={fmt_hash(pool.effective_hashrate)} />
          <Row k="Worker Status" v={pool.worker_status} color={pool.worker_status === 'online' ? color : '#5a6478'} />
          <Row k="Workers Online" v={pool.workers_online ?? '—'} />
          <Row k="Pending Balance" v={pool.pending_balance !== undefined ? pool.pending_balance.toFixed(8) : '—'} />
          <Row k="Immature Balance" v={pool.immature_balance !== undefined ? pool.immature_balance.toFixed(8) : '—'} />
          <Row k="Total Paid" v={pool.paid_total !== undefined ? pool.paid_total.toFixed(6) : '—'} />
          <Row k="Last Payout" v={pool.last_payout_ts ? new Date(pool.last_payout_ts * 1000).toLocaleString() : 'Not reported by this pool API'} />
          <Row k="Pool Difficulty" v={pool.pool_difficulty || 'Not reported by this pool API'} />
          <Row k="Pool Fee" v={pool.pool_fee_percent !== null && pool.pool_fee_percent !== undefined ? `${pool.pool_fee_percent}%` : 'See pool website'} />
        </Card>
      </div>
    </div>
  );
}

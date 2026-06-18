import React, { useEffect, useRef, useState } from 'react';
import { useMiningData } from '../context/MiningDataContext';
import { Card, KpiCard, ErrorBanner, Badge } from '../components/UIPrimitives';
import { fmt_hash, fmt_usd, fmt_usd_compact, fmt_pct_plain, coinColor } from '../utils/format';

const DEFAULT_COINS = [
  { key: 'XMR', label: 'Monero', algo: 'RandomX', pool_provider: 'MoneroOcean' },
  { key: 'ETC', label: 'Ethereum Classic', algo: 'Etchash', pool_provider: '2Miners' },
  { key: 'RVN', label: 'Ravencoin', algo: 'KawPow', pool_provider: '2Miners' },
  { key: 'ALPH', label: 'Alephium', algo: 'Blake3', pool_provider: 'HeroMiners' },
  { key: 'ERG', label: 'Ergo', algo: 'Autolykos2', pool_provider: '2Miners' },
];

export default function Dashboard() {
  const { stats, errors, actionPending, actionMessage, startMining, stopMining } = useMiningData();
  const [selectedCoin, setSelectedCoin] = useState('XMR');
  const userSelectedCoinRef = useRef(false);

  useEffect(() => {
    if (stats?.coin && !userSelectedCoinRef.current) setSelectedCoin(stats.coin);
  }, [stats?.coin]);

  const coin = stats?.coin || 'XMR';
  const availableCoins = stats?.available_coins?.length ? stats.available_coins : DEFAULT_COINS;
  const color = coinColor(coin);
  const selectedColor = coinColor(selectedCoin);
  const gpu = stats?.gpu || {};
  const xmrig = stats?.xmrig || {};
  const pool = stats?.pool || {};
  const market = stats?.market || {};
  const acceptedRate = (xmrig.accepted_shares || 0) + (xmrig.rejected_shares || 0) > 0
    ? (xmrig.accepted_shares / ((xmrig.accepted_shares || 0) + (xmrig.rejected_shares || 0))) * 100
    : null;
  const selectedCoinInfo = availableCoins.find((c) => c.key === selectedCoin) || DEFAULT_COINS[0];

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '32px 32px 60px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 18, marginBottom: '24px', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: 800, margin: 0 }}>Dashboard</h1>
          <div style={{ fontSize: '13px', color: '#5a6478', marginTop: '4px' }}>
            {stats ? `${stats.coin_label} (${stats.algo}) · ${stats.network?.network_difficulty ? 'network synced' : 'live rig telemetry'}` : 'connecting to backend'}
          </div>
        </div>
        <div style={controlPanelStyle(selectedColor)}>
          <div style={{ fontSize: '10px', color: '#8b95a8', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
            Mining Control
          </div>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <select
                value={selectedCoin}
                onChange={(event) => {
                  userSelectedCoinRef.current = true;
                  setSelectedCoin(event.target.value);
                }}
                disabled={actionPending}
                style={selectStyle(selectedColor)}
                aria-label="Mining coin"
              >
                {availableCoins.map((c) => (
                  <option key={c.key} value={c.key}>{c.key} - {c.label}</option>
                ))}
              </select>
              <span style={{ color: '#5a6478', fontSize: '11px', fontFamily: 'JetBrains Mono, monospace' }}>
                {selectedCoinInfo.algo} via {selectedCoinInfo.pool_provider}
              </span>
            </div>
            <button
              onClick={() => startMining(selectedCoin).catch(() => {})}
              disabled={actionPending}
              style={btnStyle(selectedColor, true, actionPending)}
            >
              {stats?.running && selectedCoin !== coin ? `Switch to ${selectedCoin}` : `Start ${selectedCoin}`}
            </button>
            <button
              onClick={() => stopMining().catch(() => {})}
              disabled={actionPending}
              style={btnStyle('#ff1744', Boolean(stats?.running), actionPending)}
            >
              Stop Mining
            </button>
          </div>
          {actionMessage && (
            <div style={{
              color: actionMessage.toLowerCase().includes('failed') || actionMessage.toLowerCase().includes('not found') ? '#ff8a65' : '#8b95a8',
              fontSize: '12px',
              fontFamily: 'JetBrains Mono, monospace',
            }}>
              {actionMessage}
            </div>
          )}
        </div>
      </div>

      {!stats && (
        <Card accent={selectedColor} style={{ marginBottom: 18 }}>
          <div style={{ color: '#8b95a8', fontSize: 13 }}>
            Connecting to backend. The mining controls above stay available and will send commands as soon as the backend responds.
          </div>
        </Card>
      )}

      <ErrorBanner errors={errors} />

      {stats && (
        <>
      {/* Core KPI Cards */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', marginBottom: '8px' }}>
        <KpiCard label="Current Coin" icon="◈" value={coin} sub={stats.algo} color={color} />
        <KpiCard label="Current Hashrate" icon="⚡" value={fmt_hash(xmrig.hashrate_1m)} sub={`avg 10m: ${fmt_hash(xmrig.hashrate_10m)}`} />
        <KpiCard label="Power Usage" icon="⚙" value={gpu.power_draw ? `${gpu.power_draw.toFixed(0)} W` : '—'} sub={gpu.power_limit ? `limit ${gpu.power_limit.toFixed(0)} W` : ''} />
        <KpiCard label="Daily Revenue" icon="$" value={market.price_usd ? '— ' : '—'} sub="profitability math not wired yet" color="#5a6478" />
        <KpiCard label="Daily Profit" icon="◇" value="—" sub="power-cost calc not yet enabled" color="#5a6478" />
        <KpiCard label="GPU Temperature" icon="🌡" value={gpu.temp ? `${gpu.temp.toFixed(0)}°C` : '—'} sub={gpu.warning ? 'running hot' : 'nominal'} color={gpu.warning ? '#ff1744' : '#00e676'} />
        <KpiCard label="Accepted Share Rate" icon="✓" value={acceptedRate !== null ? fmt_pct_plain(acceptedRate) : '—'} sub={`${xmrig.accepted_shares || 0} accepted`} />
        <KpiCard label="Worker Status" icon="●" value={pool.worker_status || 'unknown'} sub={pool.pool_name} color={pool.worker_status === 'online' ? color : '#5a6478'} />
      </div>

      {/* Quick glance: hardware + pool + market side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginTop: '28px' }}>
        <Card title="Hardware Snapshot">
          <Row k="GPU" v={gpu.name || '—'} />
          <Row k="GPU Util" v={gpu.gpu_util !== undefined ? `${gpu.gpu_util.toFixed(0)}%` : '—'} />
          <Row k="VRAM" v={gpu.mem_used && gpu.mem_total ? `${(gpu.mem_used / 1024).toFixed(1)} / ${(gpu.mem_total / 1024).toFixed(1)} GB` : '—'} />
          <Row k="Fan Speed" v={gpu.fan_speed !== undefined ? `${gpu.fan_speed.toFixed(0)}%` : '—'} />
          <Row k="CPU Usage" v={stats.cpu?.usage_percent !== undefined ? `${stats.cpu.usage_percent.toFixed(0)}%` : '—'} />
          <Row k="System Uptime" v={stats.system?.system_uptime_seconds ? `${Math.floor(stats.system.system_uptime_seconds / 3600)}h` : '—'} />
        </Card>

        <Card title="Pool Snapshot">
          <Row k="Pool" v={pool.pool_name || '—'} />
          <Row k="Pool Hashrate" v={fmt_hash(pool.pool_hashrate)} />
          <Row k="Workers Online" v={pool.workers_online ?? '—'} />
          <Row k="Pending Balance" v={pool.pending_balance !== undefined ? pool.pending_balance.toFixed(8) : '—'} />
          <Row k="Paid Total" v={pool.paid_total !== undefined ? pool.paid_total.toFixed(6) : '—'} />
          {pool.error && <div style={{ marginTop: '8px' }}><Badge color="#ff8a65" bg="#2a1410">{pool.error}</Badge></div>}
        </Card>

        <Card title="Coin & Market">
          <Row k="Price (USD)" v={market.price_usd ? fmt_usd(market.price_usd) : '—'} />
          <Row k="Market Cap" v={market.market_cap_usd ? fmt_usd_compact(market.market_cap_usd) : '—'} />
          <Row k="24h Volume" v={market.volume_24h_usd ? fmt_usd_compact(market.volume_24h_usd) : '—'} />
          <Row k="24h Change" v={market.change_24h_percent !== null && market.change_24h_percent !== undefined ? fmt_pct_plain(market.change_24h_percent) : '—'}
            color={market.change_24h_percent > 0 ? '#00e676' : market.change_24h_percent < 0 ? '#ff1744' : undefined} />
          <Row k="Block Height" v={stats.network?.block_height ?? 'unavailable from pool'} />
        </Card>
      </div>
        </>
      )}
    </div>
  );
}

const Row = ({ k, v, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid #181d25', fontSize: '13px' }}>
    <span style={{ color: '#8b95a8' }}>{k}</span>
    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: color || '#e8eaf0' }}>{v}</span>
  </div>
);

const controlPanelStyle = (color) => ({
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
  alignItems: 'flex-end',
  background: '#111418',
  border: `1px solid ${color}`,
  borderRadius: '8px',
  padding: '12px',
  minWidth: '360px',
  maxWidth: '100%',
});

const btnStyle = (color, filled, disabled = false) => ({
  background: filled ? color : 'transparent',
  color: filled ? '#0a0d12' : color,
  border: `1px solid ${color}`,
  borderRadius: '7px',
  padding: '9px 18px',
  fontWeight: 700,
  fontSize: '13px',
  cursor: disabled ? 'wait' : 'pointer',
  opacity: disabled ? 0.65 : 1,
  fontFamily: 'JetBrains Mono, monospace',
});

const selectStyle = (color) => ({
  height: '36px',
  minWidth: '190px',
  background: '#0d1015',
  color: '#e8eaf0',
  border: `1px solid ${color}`,
  borderRadius: '7px',
  padding: '0 12px',
  fontWeight: 700,
  fontSize: '13px',
  cursor: 'pointer',
  fontFamily: 'JetBrains Mono, monospace',
});

import React from 'react';
import { useMiningData } from '../context/MiningDataContext';
import { Card, ErrorBanner } from '../components/UIPrimitives';
import { fmt_usd, fmt_usd_compact, fmt_pct_plain } from '../utils/format';

const Row = ({ k, v, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid #181d25', fontSize: '13px' }}>
    <span style={{ color: '#8b95a8' }}>{k}</span>
    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: color || '#e8eaf0' }}>{v}</span>
  </div>
);

export default function NetworkCoin() {
  const { stats, errors } = useMiningData();
  if (!stats) return <div style={{ padding: 40, color: '#5a6478' }}>Connecting…</div>;
  const market = stats.market || {};
  const network = stats.network || {};

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '32px 32px 60px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: 800, margin: '0 0 24px' }}>Network &amp; Coin Metrics — {stats.coin}</h1>
      <ErrorBanner errors={errors} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
        <Card title="Coin Market Data (CoinGecko, refreshes every ~4 min)">
          <Row k="Price" v={market.price_usd ? fmt_usd(market.price_usd, market.price_usd < 1 ? 6 : 2) : '—'} />
          <Row k="Market Cap" v={market.market_cap_usd ? fmt_usd_compact(market.market_cap_usd) : '—'} />
          <Row k="24h Volume" v={market.volume_24h_usd ? fmt_usd_compact(market.volume_24h_usd) : '—'} />
          <Row k="24h Change" v={market.change_24h_percent !== null && market.change_24h_percent !== undefined ? fmt_pct_plain(market.change_24h_percent) : '—'}
            color={market.change_24h_percent > 0 ? '#00e676' : market.change_24h_percent < 0 ? '#ff1744' : undefined} />
        </Card>

        <Card title="Network Stats (from pool APIs — coverage varies by pool)">
          <Row k="Block Height" v={network.block_height ?? 'Not exposed by this pool API'} />
          <Row k="Network Difficulty" v={network.network_difficulty ?? 'Not exposed by this pool API'} />
          <Row k="Network Hashrate" v={network.network_hashrate ?? 'Not exposed by this pool API'} />
          <Row k="Block Reward" v={network.block_reward ?? 'Not available yet'} />
          <Row k="Block Time" v={network.block_time_seconds ? `${network.block_time_seconds}s` : 'Not available yet'} />
          {stats.coin === 'XMR' && (
            <div style={{ marginTop: 10, fontSize: 12, color: '#5a6478' }}>
              MoneroOcean's miner-stats API doesn't expose XMR network difficulty/hashrate — this is a pool API limitation, not a bug.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

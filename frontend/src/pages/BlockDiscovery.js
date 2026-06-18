import React, { useEffect, useState, useCallback } from 'react';
import { useMiningData, API_BASE } from '../context/MiningDataContext';
import { Card, ErrorBanner, EmptyState } from '../components/UIPrimitives';
import { coinColor, fmt_datetime } from '../utils/format';

export default function BlockDiscovery() {
  const { stats, errors } = useMiningData();
  const [blocks, setBlocks] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchBlocks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/history/blocks?limit=50`);
      const data = await res.json();
      setBlocks(data.blocks || []);
    } catch (_) {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchBlocks();
    const t = setInterval(fetchBlocks, 15000);
    return () => clearInterval(t);
  }, [fetchBlocks]);

  if (!stats) return <div style={{ padding: 40, color: '#5a6478' }}>Connecting…</div>;
  const color = coinColor(stats.coin);

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '32px 32px 60px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: 800, margin: '0 0 8px' }}>Block Discovery</h1>
      <div style={{ fontSize: '13px', color: '#5a6478', marginBottom: '24px' }}>
        Triggers only on a real pool-confirmed block — no demo button by design.
      </div>
      <ErrorBanner errors={errors} />

      <Card title="Your Chain">
        <ChainStrip blocks={blocks} color={color} />
      </Card>

      <div style={{ marginTop: '16px' }}>
        <Card title="Confirmed Blocks Found">
          {loading ? (
            <div style={{ color: '#5a6478', fontSize: 13 }}>Loading…</div>
          ) : blocks.length === 0 ? (
            <EmptyState message="No blocks found yet. This list fills in automatically the moment a pool confirms your address found one." />
          ) : (
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ textAlign: 'left', color: '#5a6478', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  <th style={{ padding: '6px 0' }}>Coin</th>
                  <th>Pool</th>
                  <th>Height</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {blocks.map((b) => (
                  <tr key={b.id} style={{ borderTop: '1px solid #181d25' }}>
                    <td style={{ padding: '8px 0', color: coinColor(b.coin), fontFamily: 'JetBrains Mono, monospace' }}>{b.coin}</td>
                    <td style={{ color: '#8b95a8' }}>{b.pool_name}</td>
                    <td style={{ fontFamily: 'JetBrains Mono, monospace' }}>{b.block_height ?? '—'}</td>
                    <td style={{ color: '#5a6478' }}>{fmt_datetime(new Date(b.ts * 1000).toISOString())}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}

function ChainStrip({ blocks, color }) {
  // Show the last 12 blocks (or placeholders) as a connected chain visualization
  const display = blocks.slice(0, 12).reverse();
  const placeholders = Math.max(0, 6 - display.length);

  return (
    <div style={{ display: 'flex', alignItems: 'center', overflowX: 'auto', padding: '10px 0' }}>
      {Array.from({ length: placeholders }).map((_, i) => (
        <React.Fragment key={`ph-${i}`}>
          <div style={chainBlockStyle('#1a2128', '#2a3340')}>·</div>
          {i < placeholders - 1 && <Link />}
        </React.Fragment>
      ))}
      {display.map((b, i) => (
        <React.Fragment key={b.id}>
          {(placeholders > 0 || i > 0) && <Link />}
          <div style={chainBlockStyle(`${coinColor(b.coin)}22`, coinColor(b.coin))} title={`${b.coin} #${b.block_height}`}>
            ★
          </div>
        </React.Fragment>
      ))}
      {display.length === 0 && placeholders === 0 && (
        <div style={{ color: '#5a6478', fontSize: 13 }}>No chain data yet.</div>
      )}
    </div>
  );
}

const Link = () => <div style={{ width: '20px', height: '2px', background: '#2a3340', flexShrink: 0 }} />;

const chainBlockStyle = (bg, border) => ({
  width: '44px', height: '44px', borderRadius: '8px', flexShrink: 0,
  background: bg, border: `1.5px solid ${border}`,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontSize: '14px', color: border, fontWeight: 700,
});

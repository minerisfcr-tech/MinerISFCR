import React, { useEffect, useState, useCallback } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { API_BASE } from '../context/MiningDataContext';
import { Card, EmptyState } from '../components/UIPrimitives';

const RANGE_OPTIONS = [
  { label: '1h', hours: 1 },
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
  { label: '7d', hours: 24 * 7 },
];

export default function History() {
  const [hours, setHours] = useState(24);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/history/snapshots?hours=${hours}`);
      const data = await res.json();
      const formatted = (data.snapshots || []).map((s) => ({
        ...s,
        time: new Date(s.ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }));
      setRows(formatted);
    } catch (_) {}
    setLoading(false);
  }, [hours]);

  useEffect(() => {
    fetchHistory();
    const t = setInterval(fetchHistory, 30000);
    return () => clearInterval(t);
  }, [fetchHistory]);

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '32px 32px 60px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 800, margin: 0 }}>Historical Analytics</h1>
        <div style={{ display: 'flex', gap: '6px' }}>
          {RANGE_OPTIONS.map((opt) => (
            <button key={opt.label} onClick={() => setHours(opt.hours)} style={{
              background: hours === opt.hours ? '#00e676' : 'transparent',
              color: hours === opt.hours ? '#0a0d12' : '#8b95a8',
              border: '1px solid #1e2530', borderRadius: '6px', padding: '6px 12px',
              fontSize: '12px', cursor: 'pointer', fontFamily: 'JetBrains Mono, monospace',
            }}>{opt.label}</button>
          ))}
        </div>
      </div>

      {loading && rows.length === 0 ? (
        <div style={{ color: '#5a6478' }}>Loading history…</div>
      ) : rows.length === 0 ? (
        <EmptyState message="No history yet — the backend logs one snapshot per minute, so data will appear shortly after the miner starts." />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <Card title="Hashrate Trend (H/s)">
            <Chart data={rows} dataKey="hashrate_1m" color="#00e676" />
          </Card>
          <Card title="GPU Temperature Trend (°C)">
            <Chart data={rows} dataKey="gpu_temp" color="#ff6600" />
          </Card>
          <Card title="GPU Power Draw Trend (W)">
            <Chart data={rows} dataKey="gpu_power_draw" color="#2196f3" />
          </Card>
          <Card title="Coin Price Trend (USD)">
            <Chart data={rows} dataKey="price_usd" color="#ffca28" />
          </Card>
          <Card title="Accepted Shares (cumulative)">
            <Chart data={rows} dataKey="accepted_shares" color="#00e676" />
          </Card>
          <Card title="CPU Usage Trend (%)">
            <Chart data={rows} dataKey="cpu_usage_percent" color="#e040fb" />
          </Card>
        </div>
      )}
    </div>
  );
}

function Chart({ data, dataKey, color }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e2530" />
        <XAxis dataKey="time" stroke="#5a6478" fontSize={11} tick={{ fill: '#5a6478' }} />
        <YAxis stroke="#5a6478" fontSize={11} tick={{ fill: '#5a6478' }} />
        <Tooltip contentStyle={{ background: '#0d1015', border: '1px solid #1e2530', fontSize: 12 }} labelStyle={{ color: '#8b95a8' }} />
        <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

import React, { useState, useEffect, useRef, useCallback } from 'react';

// ── CONFIG ─────────────────────────────────────────────────────────────────
// Change this to your Cloudflare tunnel URL once you set it up
const API_BASE = process.env.REACT_APP_API_URL || '';
const WS_BASE = process.env.REACT_APP_WS_URL || (API_BASE
  ? API_BASE.replace(/^http/, 'ws')
  : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`);

// ── HELPERS ─────────────────────────────────────────────────────────────────
const fmt_hash = (h) => {
  if (!h || h === 0) return '0 H/s';
  if (h >= 1e6) return `${(h / 1e6).toFixed(2)} MH/s`;
  if (h >= 1e3) return `${(h / 1e3).toFixed(2)} KH/s`;
  return `${h.toFixed(1)} H/s`;
};
const fmt_uptime = (s) => {
  if (!s) return '0s';
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
};
const fmt_time = (iso) => {
  if (!iso) return '--';
  return new Date(iso).toLocaleTimeString();
};

// ── SUB-COMPONENTS ──────────────────────────────────────────────────────────
const GaugeBar = ({ value, max = 100, color = '#ff6600', label, unit = '%' }) => {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '11px', color: '#5a6478', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color }}>{value?.toFixed(1)}{unit}</span>
      </div>
      <div style={{ height: '4px', background: '#1e2530', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: '2px', transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
};

const StatBox = ({ label, value, sub, accent = false }) => (
  <div style={{
    background: '#111418', border: `1px solid ${accent ? '#7a3000' : '#1e2530'}`,
    borderRadius: '8px', padding: '14px 16px', flex: 1, minWidth: '120px',
  }}>
    <div style={{ fontSize: '10px', color: '#5a6478', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>{label}</div>
    <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '18px', color: accent ? '#ff6600' : '#e8eaf0', fontWeight: 700 }}>{value}</div>
    {sub && <div style={{ fontSize: '11px', color: '#5a6478', marginTop: '3px' }}>{sub}</div>}
  </div>
);

const ErrorBanner = ({ errors }) => {
  if (!errors || errors.length === 0) return null;
  return (
    <div style={{ marginBottom: '20px' }}>
      {errors.map((err, i) => (
        <div key={i} style={{
          background: '#1a0a0a', border: '1px solid #7a1010', borderRadius: '8px',
          padding: '10px 14px', marginBottom: '6px', display: 'flex', alignItems: 'flex-start', gap: '10px',
        }}>
          <span style={{ color: '#ff1744', fontSize: '14px', marginTop: '1px' }}>⚠</span>
          <span style={{ color: '#ffcdd2', fontSize: '13px', lineHeight: 1.4 }}>{err}</span>
        </div>
      ))}
    </div>
  );
};

const StatusDot = ({ active }) => (
  <span style={{
    display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%',
    background: active ? '#00e676' : '#5a6478',
    boxShadow: active ? '0 0 8px #00e676' : 'none',
    marginRight: '8px',
    animation: active ? 'pulse 2s infinite' : 'none',
  }} />
);

// ── MAIN APP ────────────────────────────────────────────────────────────────
export default function App() {
  const [stats, setStats] = useState(null);
  const [mining, setMining] = useState(false);
  const [selectedCoin, setSelectedCoin] = useState('XMR');
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [wsStatus, setWsStatus] = useState('connecting');
  const [errors, setErrors] = useState([]);
  const [logs, setLogs] = useState([]);
  const [logsOpen, setLogsOpen] = useState(false);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const pollRef = useRef(null);

  const applyStats = useCallback((data) => {
    setStats(data);
    setMining(Boolean(data?.running ?? data?.mining));
    setErrors(data?.errors || []);
    if (data?.coin && (data?.running ?? data?.mining)) {
      setSelectedCoin(data.coin);
    }
  }, []);

  const pollStatus = useCallback(async () => {
    try {
      const res = await fetch('/mine/status');
      if (!res.ok) return;
      const data = await res.json();
      applyStats(data);
      setWsStatus('connected');
    } catch (_) {}
  }, [applyStats]);

  const connectWS = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
    setWsStatus('connecting');
    const ws = new WebSocket(`${WS_BASE}/ws/stats`);
    wsRef.current = ws;

    ws.onopen = () => setWsStatus('connected');
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.error) {
          setErrors(prev => [...prev.slice(-4), data.error]);
          return;
        }
        applyStats(data);
        setWsStatus('connected');
      } catch (_) {}
    };
    ws.onclose = () => {
      setWsStatus('disconnected');
      reconnectRef.current = setTimeout(connectWS, 3000);
    };
    ws.onerror = () => ws.close();
  }, []);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/logs?limit_entries=20`);
      if (!res.ok) return;
      const data = await res.json();
      setLogs(data.entries || []);
    } catch (_) {}
  }, []);

  useEffect(() => {
    connectWS();
    pollStatus();
    fetchLogs();
    pollRef.current = setInterval(pollStatus, 2000);
    const logsInterval = setInterval(fetchLogs, 60000);
    return () => {
      clearTimeout(reconnectRef.current);
      clearInterval(pollRef.current);
      clearInterval(logsInterval);
      wsRef.current?.close();
    };
  }, [connectWS, pollStatus, fetchLogs]);

  const handleStart = async () => {
    setLoading(true); setActionMsg('');
    try {
      const res = await fetch(`${API_BASE}/mine/start`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ coin: selectedCoin })
      });
      const data = await res.json();
      if (!res.ok) {
        setErrors([data.detail || 'Failed to start miner.']);
      } else {
        setActionMsg(data.message);
        pollStatus();
      }
    } catch (e) {
      setErrors(['Could not reach the mining rig — is the backend running?']);
    }
    setLoading(false);
  };

  const handleStop = async () => {
    setLoading(true); setActionMsg('');
    try {
      const res = await fetch(`${API_BASE}/mine/stop`, { method: 'POST' });
      const data = await res.json();
      setActionMsg(data.message);
      pollStatus();
    } catch (e) {
      setErrors(['Could not reach the mining rig.']);
    }
    setLoading(false);
  };

  const xmrig  = stats?.xmrig  || {};
  const gpu    = stats?.gpu    || {};
  const cpu    = stats?.cpu    || {};
  const availableCoins = stats?.available_coins || [
    { key: 'XMR', label: 'Monero' },
    { key: 'ETC', label: 'Ethereum Classic' },
    { key: 'RVN', label: 'Ravencoin' },
    { key: 'ALPH', label: 'Alephium' },
    { key: 'ERG', label: 'Ergo' },
  ];

  const connColor = wsStatus === 'connected' ? '#00e676' : wsStatus === 'connecting' ? '#ffd600' : '#ff1744';

  return (
    <div style={{ minHeight: '100vh', background: '#0a0c0f', padding: '0' }}>
      {/* Top bar */}
      <div style={{
        borderBottom: '1px solid #1e2530', padding: '14px 32px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        position: 'sticky', top: 0, background: '#0a0c0f', zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'JetBrains Mono, monospace', color: '#ff6600', letterSpacing: '-0.02em' }}>⬡ ISFCR Mining Console</span>
          <span style={{ color: '#5a6478', fontSize: '13px' }}>{stats?.coin_label || ''}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <span style={{ fontSize: '12px', color: connColor, fontFamily: 'JetBrains Mono, monospace' }}>
            ● {wsStatus === 'connected' ? 'Live' : wsStatus === 'connecting' ? 'Connecting…' : 'Disconnected'}
          </span>
          <span style={{ fontSize: '11px', color: '#5a6478' }}>{fmt_time(stats?.timestamp)}</span>
        </div>
      </div>

      <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '32px 24px' }}>

        {/* Error banners */}
        <ErrorBanner errors={errors} />

        {/* Mining status + controls */}
        <div style={{
          background: '#111418', border: `1px solid ${mining ? '#7a3000' : '#1e2530'}`,
          borderRadius: '12px', padding: '24px', marginBottom: '24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '6px' }}>
              <StatusDot active={mining} />
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '20px', fontWeight: 700, color: mining ? '#ff6600' : '#5a6478' }}>
                {mining ? `Mining ${stats?.coin || ''}` : 'Miner Idle'}
              </span>
            </div>
            {mining && xmrig.pool && (
              <div style={{ fontSize: '12px', color: '#5a6478' }}>Pool: <span style={{ color: '#a0aec0' }}>{xmrig.pool}</span></div>
            )}
            {actionMsg && <div style={{ fontSize: '12px', color: '#00e676', marginTop: '4px' }}>{actionMsg}</div>}
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <select
              value={selectedCoin}
              onChange={(e) => setSelectedCoin(e.target.value)}
              disabled={loading}
              style={{
                padding: '8px 12px', borderRadius: '8px', border: '1px solid #1e2530',
                background: '#0a0c0f', color: '#e8eaf0', cursor: loading ? 'not-allowed' : 'pointer',
                fontFamily: 'JetBrains Mono, monospace', fontSize: '13px', outline: 'none',
              }}
            >
              {availableCoins.map((c) => (
                <option key={c.key} value={c.key}>{c.key} ({c.label})</option>
              ))}
            </select>
            <button
              onClick={handleStart}
              disabled={loading || (mining && selectedCoin === stats?.coin)}
              style={{
                padding: '10px 28px', borderRadius: '8px', border: 'none',
                cursor: (loading || (mining && selectedCoin === stats?.coin)) ? 'not-allowed' : 'pointer',
                background: (mining && selectedCoin === stats?.coin) ? '#1e2530' : '#ff6600',
                color: (mining && selectedCoin === stats?.coin) ? '#5a6478' : '#000',
                fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, fontSize: '13px', transition: 'all 0.2s',
              }}
            >{loading ? (mining ? 'Switching…' : 'Starting…') : (mining && selectedCoin !== stats?.coin ? `Switch to ${selectedCoin}` : 'Start Mining')}</button>
            <button
              onClick={handleStop}
              disabled={!mining || loading}
              style={{
                padding: '10px 28px', borderRadius: '8px', border: '1px solid #7a1010', cursor: !mining || loading ? 'not-allowed' : 'pointer',
                background: 'transparent', color: !mining ? '#5a6478' : '#ff1744',
                fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, fontSize: '13px', transition: 'all 0.2s',
              }}
            >{loading && mining ? 'Stopping…' : 'Stop Mining'}</button>
          </div>
        </div>

        {/* Hashrate row */}
        <div style={{ display: 'flex', gap: '14px', marginBottom: '24px', flexWrap: 'wrap' }}>
          <StatBox label="Hashrate (1 min)"  value={fmt_hash(xmrig.hashrate_1m)}  accent={mining} />
          <StatBox label="Hashrate (10 min)" value={fmt_hash(xmrig.hashrate_10m)} />
          <StatBox label="Hashrate (1 hour)" value={fmt_hash(xmrig.hashrate_1h)}  />
          <StatBox label="Uptime"            value={fmt_uptime(xmrig.uptime)}      />
        </div>

        {/* Shares row */}
        <div style={{ display: 'flex', gap: '14px', marginBottom: '24px', flexWrap: 'wrap' }}>
          <StatBox label="Accepted Shares" value={xmrig.accepted_shares ?? '—'} sub="pool accepted" />
          <StatBox label="Rejected Shares" value={xmrig.rejected_shares ?? '—'} sub="pool rejected" />
          <StatBox label="Difficulty"      value={xmrig.difficulty ? xmrig.difficulty.toLocaleString() : '—'} />
          <StatBox label="Pool Connected"  value={xmrig.connected ? 'Yes' : mining ? 'No' : '—'} />
        </div>

        {/* GPU + CPU cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>

          {/* GPU */}
          <div style={{ background: '#111418', border: '1px solid #1e2530', borderRadius: '12px', padding: '20px' }}>
            <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, fontSize: '13px', letterSpacing: '0.04em', textTransform: 'uppercase', color: '#a0aec0' }}>GPU — RTX 4090</span>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '20px', fontWeight: 700, color: gpu.temp > 82 ? '#ff1744' : '#ff6600' }}>
                {gpu.temp ?? 0}°C
              </span>
            </div>
            <GaugeBar label="GPU Utilisation" value={gpu.gpu_util ?? 0} color="#ff6600" />
            <GaugeBar label="Memory Utilisation" value={gpu.mem_util ?? 0} color="#f57c00" />
            <GaugeBar label="Fan Speed" value={gpu.fan_speed ?? 0} color="#5a6478" />
            <div style={{ display: 'flex', gap: '10px', marginTop: '12px', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, background: '#0a0c0f', borderRadius: '6px', padding: '8px 10px' }}>
                <div style={{ fontSize: '10px', color: '#5a6478', marginBottom: '2px' }}>POWER</div>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '13px' }}>{gpu.power_draw?.toFixed(0) ?? 0}W <span style={{ color: '#5a6478' }}>/ {gpu.power_limit?.toFixed(0) ?? 0}W</span></div>
              </div>
              <div style={{ flex: 1, background: '#0a0c0f', borderRadius: '6px', padding: '8px 10px' }}>
                <div style={{ fontSize: '10px', color: '#5a6478', marginBottom: '2px' }}>VRAM</div>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '13px' }}>{gpu.mem_used?.toFixed(0) ?? 0} <span style={{ color: '#5a6478' }}>/ {gpu.mem_total?.toFixed(0) ?? 0} MB</span></div>
              </div>
              <div style={{ flex: 1, background: '#0a0c0f', borderRadius: '6px', padding: '8px 10px' }}>
                <div style={{ fontSize: '10px', color: '#5a6478', marginBottom: '2px' }}>CLOCK</div>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '13px' }}>{gpu.clock_mhz?.toFixed(0) ?? 0} <span style={{ color: '#5a6478' }}>MHz</span></div>
              </div>
            </div>
          </div>

          {/* CPU */}
          <div style={{ background: '#111418', border: '1px solid #1e2530', borderRadius: '12px', padding: '20px' }}>
            <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, fontSize: '13px', letterSpacing: '0.04em', textTransform: 'uppercase', color: '#a0aec0' }}>CPU — Intel i9</span>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '20px', fontWeight: 700, color: cpu.temp > 85 ? '#ff1744' : '#e8eaf0' }}>
                {cpu.temp ?? 0}°C
              </span>
            </div>
            <GaugeBar label="CPU Usage" value={cpu.usage_percent ?? 0} color="#4fc3f7" />
            <GaugeBar label="RAM Usage" value={cpu.ram_percent ?? 0} color="#7e57c2" />
            <div style={{ display: 'flex', gap: '10px', marginTop: '12px', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, background: '#0a0c0f', borderRadius: '6px', padding: '8px 10px' }}>
                <div style={{ fontSize: '10px', color: '#5a6478', marginBottom: '2px' }}>CORES / THREADS</div>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '13px' }}>{cpu.core_count ?? 0} <span style={{ color: '#5a6478' }}>/ {cpu.thread_count ?? 0}</span></div>
              </div>
              <div style={{ flex: 1, background: '#0a0c0f', borderRadius: '6px', padding: '8px 10px' }}>
                <div style={{ fontSize: '10px', color: '#5a6478', marginBottom: '2px' }}>FREQ</div>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '13px' }}>{cpu.freq_mhz?.toFixed(0) ?? 0} <span style={{ color: '#5a6478' }}>MHz</span></div>
              </div>
              <div style={{ flex: 1, background: '#0a0c0f', borderRadius: '6px', padding: '8px 10px' }}>
                <div style={{ fontSize: '10px', color: '#5a6478', marginBottom: '2px' }}>RAM</div>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '13px' }}>{cpu.ram_used_gb ?? 0} <span style={{ color: '#5a6478' }}>/ {cpu.ram_total_gb ?? 0} GB</span></div>
              </div>
            </div>
          </div>
        </div>

        {/* Activity logs */}
        <div style={{ background: '#111418', border: '1px solid #1e2530', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
          <div
            onClick={() => setLogsOpen(!logsOpen)}
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
          >
            <span style={{ fontWeight: 600, fontSize: '13px', letterSpacing: '0.04em', textTransform: 'uppercase', color: '#a0aec0' }}>
              Activity Log <span style={{ color: '#5a6478', fontWeight: 400, textTransform: 'none' }}>· snapshot every 30 min</span>
            </span>
            <span style={{ color: '#5a6478', fontSize: '12px', fontFamily: 'JetBrains Mono, monospace' }}>{logsOpen ? '▲ collapse' : '▼ expand'}</span>
          </div>
          {logsOpen && (
            <div style={{ marginTop: '14px', maxHeight: '320px', overflowY: 'auto' }}>
              {logs.length === 0 && (
                <div style={{ color: '#5a6478', fontSize: '12px', fontFamily: 'JetBrains Mono, monospace' }}>
                  No log entries yet — the first snapshot is written 30 minutes after mining starts.
                </div>
              )}
              {logs.map((entry, i) => (
                <pre key={i} style={{
                  background: '#0a0c0f', border: '1px solid #1e2530', borderRadius: '8px',
                  padding: '12px 14px', marginBottom: '8px', fontSize: '12px', lineHeight: 1.6,
                  color: '#c5cad4', fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'pre-wrap',
                }}>{entry}</pre>
              ))}
            </div>
          )}
        </div>

        <div style={{ textAlign: 'center', color: '#2a3040', fontSize: '11px', fontFamily: 'JetBrains Mono, monospace' }}>
          ISFCR MINING CONSOLE • UPDATES EVERY 2s • {wsStatus.toUpperCase()}
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}

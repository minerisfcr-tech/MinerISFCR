export const fmt_hash = (h) => {
  if (h === null || h === undefined) return '—';
  if (h === 0) return '0 H/s';
  if (h >= 1e9) return `${(h / 1e9).toFixed(2)} GH/s`;
  if (h >= 1e6) return `${(h / 1e6).toFixed(2)} MH/s`;
  if (h >= 1e3) return `${(h / 1e3).toFixed(2)} KH/s`;
  return `${h.toFixed(1)} H/s`;
};

export const fmt_uptime = (s) => {
  if (!s) return '0s';
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
};

export const fmt_time = (iso) => {
  if (!iso) return '--';
  return new Date(iso).toLocaleTimeString();
};

export const fmt_datetime = (iso) => {
  if (!iso) return '--';
  return new Date(iso).toLocaleString();
};

export const fmt_usd = (v, decimals = 2) => {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return `$${v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
};

export const fmt_usd_compact = (v) => {
  if (v === null || v === undefined || isNaN(v)) return '—';
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(2)}K`;
  return `$${v.toFixed(2)}`;
};

export const fmt_coin = (v, decimals = 6) => {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return v.toFixed(decimals);
};

export const fmt_percent = (v, decimals = 2) => {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`;
};

export const fmt_pct_plain = (v, decimals = 1) => {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return `${v.toFixed(decimals)}%`;
};

export const fmt_bytes_gb = (gb) => {
  if (gb === null || gb === undefined) return '—';
  return `${gb.toFixed(1)} GB`;
};

export const fmt_kbps = (k) => {
  if (k === null || k === undefined) return '—';
  if (k >= 1024) return `${(k / 1024).toFixed(2)} MB/s`;
  return `${k.toFixed(1)} KB/s`;
};

export const COIN_COLORS = {
  XMR: '#ff6600',
  ETC: '#00e676',
  RVN: '#2196f3',
  ALPH: '#e040fb',
  ERG: '#ffca28',
};

export const coinColor = (coin) => COIN_COLORS[coin] || '#00e676';

import React from 'react';

export const Card = ({ title, children, accent, style }) => (
  <div style={{
    background: '#111418', border: `1px solid ${accent || '#1e2530'}`,
    borderRadius: '10px', padding: '18px 20px', ...style,
  }}>
    {title && (
      <div style={{
        fontSize: '11px', color: '#5a6478', textTransform: 'uppercase',
        letterSpacing: '0.08em', marginBottom: '14px', fontWeight: 600,
      }}>{title}</div>
    )}
    {children}
  </div>
);

export const GaugeBar = ({ value, max = 100, color = '#ff6600', label, unit = '%', decimals = 1 }) => {
  const safeValue = value || 0;
  const pct = Math.min(100, (safeValue / max) * 100);
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '11px', color: '#5a6478', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color }}>
          {value === null || value === undefined ? '—' : safeValue.toFixed(decimals)}{unit}
        </span>
      </div>
      <div style={{ height: '4px', background: '#1e2530', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: '2px', transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
};

export const StatBox = ({ label, value, sub, accent = false, color }) => (
  <div style={{
    background: '#111418', border: `1px solid ${accent ? '#7a3000' : '#1e2530'}`,
    borderRadius: '8px', padding: '14px 16px', flex: 1, minWidth: '130px',
  }}>
    <div style={{ fontSize: '10px', color: '#5a6478', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>{label}</div>
    <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '18px', color: color || (accent ? '#ff6600' : '#e8eaf0'), fontWeight: 700 }}>{value}</div>
    {sub && <div style={{ fontSize: '11px', color: '#5a6478', marginTop: '3px' }}>{sub}</div>}
  </div>
);

export const KpiCard = ({ icon, label, value, sub, color = '#00e676' }) => (
  <div style={{
    background: 'linear-gradient(180deg, #131820 0%, #0e1116 100%)',
    border: '1px solid #1e2530', borderRadius: '12px', padding: '16px 18px',
    display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '150px', flex: 1,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span style={{ fontSize: '10px', color: '#5a6478', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>{label}</span>
      {icon && <span style={{ fontSize: '14px', opacity: 0.7 }}>{icon}</span>}
    </div>
    <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '22px', fontWeight: 700, color }}>{value}</div>
    {sub && <div style={{ fontSize: '11px', color: '#5a6478' }}>{sub}</div>}
  </div>
);

export const ErrorBanner = ({ errors }) => {
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

export const StatusDot = ({ active, color }) => (
  <span style={{
    display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%',
    background: active ? (color || '#00e676') : '#5a6478',
    boxShadow: active ? `0 0 8px ${color || '#00e676'}` : 'none',
    marginRight: '8px',
    animation: active ? 'pulse 2s infinite' : 'none',
    flexShrink: 0,
  }} />
);

export const Badge = ({ children, color = '#5a6478', bg = '#1e2530' }) => (
  <span style={{
    display: 'inline-block', padding: '3px 9px', borderRadius: '5px',
    fontSize: '11px', fontWeight: 600, color, background: bg,
    fontFamily: 'JetBrains Mono, monospace',
  }}>{children}</span>
);

export const SectionHeading = ({ children }) => (
  <h2 style={{
    fontSize: '13px', color: '#8b95a8', textTransform: 'uppercase',
    letterSpacing: '0.1em', fontWeight: 700, margin: '32px 0 14px 0',
    borderBottom: '1px solid #1e2530', paddingBottom: '10px',
  }}>{children}</h2>
);

export const EmptyState = ({ message }) => (
  <div style={{
    textAlign: 'center', padding: '40px 20px', color: '#5a6478',
    fontSize: '13px', border: '1px dashed #1e2530', borderRadius: '10px',
  }}>{message}</div>
);

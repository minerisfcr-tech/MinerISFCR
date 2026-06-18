import React, { useEffect, useState } from 'react';
import { useMiningData } from '../context/MiningDataContext';
import { coinColor } from '../utils/format';

function BlockFoundToast({ event, onDismiss, topOffset }) {
  const [phase, setPhase] = useState('entering'); // entering -> settled -> leaving
  const color = coinColor(event.coin);

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('settled'), 600);
    const t2 = setTimeout(() => setPhase('leaving'), 9000);
    const t3 = setTimeout(() => onDismiss(event.timestamp), 9600);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [event.timestamp, onDismiss]);

  return (
    <div
      style={{
        position: 'fixed', top: `${topOffset}px`, right: '24px', zIndex: 9999,
        width: '380px', background: '#0d1015', border: `1px solid ${color}`,
        borderRadius: '14px', padding: '20px', boxShadow: `0 8px 40px ${color}55, 0 0 0 1px ${color}33`,
        opacity: phase === 'leaving' ? 0 : 1,
        transform: phase === 'entering' ? 'translateX(40px) scale(0.96)' : 'translateX(0) scale(1)',
        transition: 'all 0.5s cubic-bezier(0.22, 1, 0.36, 1)',
        fontFamily: 'JetBrains Mono, monospace',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <span style={{ fontSize: '20px' }}>⛏</span>
        <span style={{ fontWeight: 800, fontSize: '14px', color, letterSpacing: '0.04em' }}>BLOCK FOUND</span>
        <button onClick={() => onDismiss(event.timestamp)} style={{
          marginLeft: 'auto', background: 'none', border: 'none', color: '#5a6478',
          cursor: 'pointer', fontSize: '14px', padding: '2px 6px',
        }}>✕</button>
      </div>

      {/* Chain-link animation: blocks sliding in and "locking" onto the chain */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '14px', overflow: 'hidden' }}>
        {[0, 1, 2].map((i) => (
          <React.Fragment key={i}>
            <div style={{
              width: '34px', height: '34px', borderRadius: '6px',
              background: i === 2 ? `${color}22` : '#1a2128',
              border: `1.5px solid ${i === 2 ? color : '#2a3340'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '10px', color: i === 2 ? color : '#5a6478', fontWeight: 700,
              animation: i === 2 ? `blockPop 0.6s ease ${0.2 + i * 0.15}s` : 'none',
              flexShrink: 0,
            }}>
              {i === 2 ? '★' : ''}
            </div>
            {i < 2 && <div style={{ width: '14px', height: '2px', background: '#2a3340', flexShrink: 0 }} />}
          </React.Fragment>
        ))}
        <div style={{ width: '14px', height: '2px', background: color, flexShrink: 0, boxShadow: `0 0 6px ${color}` }} />
        <div style={{
          flex: 1, height: '2px', background: `linear-gradient(90deg, ${color}, transparent)`,
        }} />
      </div>

      <div style={{ fontSize: '13px', color: '#e8eaf0', marginBottom: '4px' }}>
        Your rig found a <span style={{ color, fontWeight: 700 }}>{event.coin}</span> block
        {event.block_height ? <> at height <span style={{ color: '#e8eaf0', fontWeight: 700 }}>{event.block_height.toLocaleString()}</span></> : null}
      </div>
      <div style={{ fontSize: '11px', color: '#5a6478' }}>
        via {event.pool_name} · {new Date(event.timestamp).toLocaleTimeString()}
      </div>

      <style>{`
        @keyframes blockPop {
          0% { transform: scale(0.5); opacity: 0; }
          60% { transform: scale(1.15); opacity: 1; }
          100% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

export default function BlockFoundOverlay() {
  const { blockEvents, dismissBlockEvent } = useMiningData();
  // Stack toasts vertically if multiple arrive close together
  return (
    <>
      {blockEvents.map((event, i) => (
        <BlockFoundToast key={event.timestamp} event={event} onDismiss={dismissBlockEvent} topOffset={24 + i * 168} />
      ))}
    </>
  );
}

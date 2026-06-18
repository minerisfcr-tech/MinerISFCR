import React from 'react';
import { useMiningData } from '../context/MiningDataContext';
import { Card, GaugeBar, ErrorBanner } from '../components/UIPrimitives';
import { fmt_uptime, fmt_kbps, fmt_bytes_gb } from '../utils/format';

const Row = ({ k, v }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid #181d25', fontSize: '13px' }}>
    <span style={{ color: '#8b95a8' }}>{k}</span>
    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: '#e8eaf0' }}>{v}</span>
  </div>
);

export default function Hardware() {
  const { stats, errors } = useMiningData();
  if (!stats) return <div style={{ padding: 40, color: '#5a6478' }}>Connecting…</div>;
  const gpu = stats.gpu || {};
  const cpu = stats.cpu || {};
  const system = stats.system || {};

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '32px 32px 60px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: 800, margin: '0 0 24px' }}>Hardware Metrics</h1>
      <ErrorBanner errors={errors} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
        <Card title={`GPU — ${gpu.name || 'unknown'}`}>
          <GaugeBar label="GPU Utilization" value={gpu.gpu_util} color="#00e676" />
          <GaugeBar label="Memory Utilization" value={gpu.mem_util} color="#2196f3" />
          <GaugeBar label="Temperature" value={gpu.temp} max={100} unit="°C" color={gpu.warning ? '#ff1744' : '#ff6600'} />
          <GaugeBar label="Fan Speed" value={gpu.fan_speed} color="#8b95a8" />
          <Row k="Hotspot Temp" v={gpu.hotspot_supported ? `${gpu.hotspot_temp?.toFixed(0)}°C` : 'Not exposed by nvidia-smi on this GPU'} />
          <Row k="Core Clock" v={gpu.clock_mhz ? `${gpu.clock_mhz.toFixed(0)} MHz` : '—'} />
          <Row k="Memory Clock" v={gpu.mem_clock_mhz ? `${gpu.mem_clock_mhz.toFixed(0)} MHz` : '—'} />
          <Row k="Power Draw" v={gpu.power_draw ? `${gpu.power_draw.toFixed(0)} W / ${gpu.power_limit?.toFixed(0)} W limit` : '—'} />
          <Row k="VRAM Used" v={gpu.mem_used ? `${(gpu.mem_used / 1024).toFixed(2)} GB / ${(gpu.mem_total / 1024).toFixed(2)} GB` : '—'} />
        </Card>

        <Card title="CPU">
          <GaugeBar label="CPU Utilization" value={cpu.usage_percent} color="#00e676" />
          <GaugeBar label="Temperature" value={cpu.temp} max={100} unit="°C" color={cpu.temp > 85 ? '#ff1744' : '#ff6600'} />
          <Row k="Frequency" v={cpu.freq_mhz ? `${cpu.freq_mhz.toFixed(0)} MHz` : '—'} />
          <Row k="Cores" v={cpu.core_count ?? '—'} />
          <Row k="Threads" v={cpu.thread_count ?? '—'} />
          <Row k="RAM Used" v={cpu.ram_used_gb !== undefined ? `${cpu.ram_used_gb.toFixed(1)} GB / ${cpu.ram_total_gb?.toFixed(1)} GB` : '—'} />
        </Card>

        <Card title="Disk">
          <GaugeBar label="Disk Usage" value={system.disk_percent} color="#2196f3" />
          <Row k="Used" v={fmt_bytes_gb(system.disk_used_gb)} />
          <Row k="Total" v={fmt_bytes_gb(system.disk_total_gb)} />
        </Card>

        <Card title="Network & Uptime">
          <Row k="Upload" v={fmt_kbps(system.upload_kbps)} />
          <Row k="Download" v={fmt_kbps(system.download_kbps)} />
          <Row k="Total Sent" v={fmt_bytes_gb(system.total_sent_gb)} />
          <Row k="Total Received" v={fmt_bytes_gb(system.total_recv_gb)} />
          <Row k="System Uptime" v={fmt_uptime(system.system_uptime_seconds)} />
          <Row k="Miner Uptime" v={fmt_uptime(stats.xmrig?.uptime)} />
        </Card>
      </div>
    </div>
  );
}

import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';

const isBrowser = typeof window !== 'undefined';
const configuredApiBase = process.env.REACT_APP_API_URL || '';
const configuredWsBase = process.env.REACT_APP_WS_URL || '';

function isUnsafeLocalOverride(url) {
  if (!isBrowser || !url) return false;
  try {
    const parsed = new URL(url, window.location.origin);
    const pageHost = window.location.hostname;
    const localApiHost = ['localhost', '127.0.0.1', '0.0.0.0'].includes(parsed.hostname);
    return localApiHost && !['localhost', '127.0.0.1', '0.0.0.0'].includes(pageHost);
  } catch (_) {
    return false;
  }
}

const API_BASE = isUnsafeLocalOverride(configuredApiBase) ? '' : configuredApiBase;
const WS_BASE = isUnsafeLocalOverride(configuredWsBase)
  ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
  : configuredWsBase
    || (API_BASE
        ? API_BASE.replace(/^https/, 'wss').replace(/^http/, 'ws')
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`);

export { API_BASE, WS_BASE };

const MiningDataContext = createContext(null);

export function MiningDataProvider({ children }) {
  const [stats, setStats] = useState(null);
  const [connected, setConnected] = useState(false);
  const [errors, setErrors] = useState([]);
  const [actionPending, setActionPending] = useState(false);
  const [actionMessage, setActionMessage] = useState('');
  const [blockEvents, setBlockEvents] = useState([]); // queue of recent block-found events, for the animation
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const pollRef = useRef(null);
  const lastBlockTsRef = useRef(null);

  const handlePayload = useCallback((payload) => {
    setStats(payload);
    setConnected(true);
    setErrors(payload.errors || []);
    if (payload.new_block_event) {
      const ts = payload.new_block_event.timestamp;
      if (ts !== lastBlockTsRef.current) {
        lastBlockTsRef.current = ts;
        setBlockEvents((prev) => [payload.new_block_event, ...prev].slice(0, 20));
      }
    }
  }, []);

  const pollStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/mine/status`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      handlePayload(data);
    } catch (e) {
      setConnected(false);
      setErrors([`Could not reach the backend from this page — run start.sh and wait for it to finish starting up.`]);
    }
  }, [handlePayload]);

  const connectWS = useCallback(() => {
    try {
      const ws = new WebSocket(`${WS_BASE}/ws/stats`);
      wsRef.current = ws;
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handlePayload(data);
        } catch (_) {}
      };
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        clearTimeout(reconnectRef.current);
        reconnectRef.current = setTimeout(connectWS, 3000);
      };
      ws.onerror = () => ws.close();
    } catch (_) {
      reconnectRef.current = setTimeout(connectWS, 3000);
    }
  }, [handlePayload]);

  useEffect(() => {
    connectWS();
    pollStatus();
    pollRef.current = setInterval(pollStatus, 5000); // fallback poll in case WS drops silently
    return () => {
      clearTimeout(reconnectRef.current);
      clearInterval(pollRef.current);
      wsRef.current?.close();
    };
  }, [connectWS, pollStatus]);

  const runMiningAction = useCallback(async (action, options = {}) => {
    setActionPending(true);
    setActionMessage('');
    try {
      const res = await fetch(`${API_BASE}/mine/${action}`, options);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || data.message || `Mining action failed with HTTP ${res.status}`);
      }
      setActionMessage(data.message || 'Mining command sent.');
      await pollStatus();
      return data;
    } catch (e) {
      const message = e.message || 'Mining command failed.';
      setActionMessage(message);
      setErrors((prev) => [message, ...prev.filter((err) => err !== message)].slice(0, 5));
      throw e;
    } finally {
      setActionPending(false);
    }
  }, [pollStatus]);

  const startMining = useCallback((coin) => runMiningAction('start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ coin }),
  }), [runMiningAction]);

  const stopMining = useCallback(() => runMiningAction('stop', { method: 'POST' }), [runMiningAction]);

  const dismissBlockEvent = useCallback((ts) => {
    setBlockEvents((prev) => prev.filter((e) => e.timestamp !== ts));
  }, []);

  return (
    <MiningDataContext.Provider value={{
      stats, connected, errors, actionPending, actionMessage, blockEvents, dismissBlockEvent, startMining, stopMining,
    }}>
      {children}
    </MiningDataContext.Provider>
  );
}

export function useMiningData() {
  const ctx = useContext(MiningDataContext);
  if (!ctx) throw new Error('useMiningData must be used within MiningDataProvider');
  return ctx;
}

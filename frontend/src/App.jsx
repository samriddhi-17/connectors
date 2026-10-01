import React, { useCallback, useEffect, useRef, useState } from 'react';
import { alertFileList, fetchConnectors, fetchHealth, grafanaUrl } from './api.js';
import ConnectorCard from './components/ConnectorCard.jsx';

const POLL_MS = 5000;

export default function App() {
  const [health, setHealth] = useState(null);
  const [connectors, setConnectors] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState('');
  const [lastSync, setLastSync] = useState(null);
  const timer = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [h, c, a] = await Promise.all([fetchHealth(), fetchConnectors(), alertFileList()]);
      setHealth(h);
      setConnectors(c.connectors);
      setAlerts(a.alerts);
      setError('');
      setLastSync(new Date());
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    timer.current = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer.current);
  }, [refresh]);

  const statusClass = health?.status || 'unknown';

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>Connects</h1>
          <p className="subtitle">
            React + FastAPI demo · Aerospike &amp; Yugabyte connectors · Grafana · OpenSRE
          </p>
        </div>
        <div className="topbar-right">
          <span className={`badge badge-${statusClass}`}>{statusClass}</span>
          <a className="btn" href={grafanaUrl()} target="_blank" rel="noreferrer">
            Open Grafana
          </a>
          <button className="btn" onClick={refresh}>
            Refresh
          </button>
        </div>
      </header>

      {error && <div className="error">Backend unreachable: {error}</div>}

      <section className="grid">
        {connectors.map((c) => (
          <ConnectorCard key={c.name} connector={c} />
        ))}
        {connectors.length === 0 && !error && <p className="muted">No connectors enabled.</p>}
      </section>

      <footer className="foot">
        {lastSync && <span>Last sync: {lastSync.toLocaleTimeString()}</span>}
        <span>
          OpenSRE alerts on disk: {alerts.length}
          {alerts.length > 0 && (
            <ul className="alert-list">
              {alerts.map((a) => (
                <li key={a.file}>{a.file}</li>
              ))}
            </ul>
          )}
        </span>
      </footer>
    </div>
  );
}
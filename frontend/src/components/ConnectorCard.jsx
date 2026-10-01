import React, { useState } from 'react';
import { runQuery } from '../api.js';

const OPERATIONS = {
  aerospike: [
    { id: 'get', label: 'get' },
    { id: 'put', label: 'put' },
  ],
  yugabyte: [
    { id: 'select', label: 'select' },
    { id: 'upsert', label: 'upsert' },
    { id: 'list', label: 'list' },
  ],
};

export default function ConnectorCard({ connector }) {
  const { name, kind, status, latency_ms, detail, endpoint, database, table, namespace, set: setName } = connector;
  const [operation, setOperation] = useState(OPERATIONS[name]?.[0]?.id || 'get');
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [queryError, setQueryError] = useState('');

  const ops = OPERATIONS[name] || [];

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setQueryError('');
    setResult(null);
    try {
      const payload = { key, value };
      const res = await runQuery(name, operation, payload);
      setResult(res);
    } catch (err) {
      setQueryError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`card card-${status}`}>
      <div className="card-head">
        <h2>{name}</h2>
        <span className={`badge badge-${status}`}>{status}</span>
      </div>
      <p className="muted">
        kind: {kind} · endpoint: {endpoint || 'n/a'}
        {database && ` · db: ${database} (${table})`}
        {namespace && ` · ns: ${namespace}/${setName}`}
      </p>
      <p className="detail" title={detail}>
        {detail || '—'}
      </p>
      {typeof latency_ms === 'number' && <p className="muted">check: {latency_ms.toFixed(1)} ms</p>}

      <form className="query" onSubmit={submit}>
        <select value={operation} onChange={(e) => setOperation(e.target.value)} disabled={ops.length === 0}>
          {ops.map((op) => (
            <option key={op.id} value={op.id}>
              {op.label}
            </option>
          ))}
        </select>
        <input placeholder="key" value={key} onChange={(e) => setKey(e.target.value)} />
        <input placeholder="value" value={value} onChange={(e) => setValue(e.target.value)} />
        <button type="submit" disabled={busy || ops.length === 0}>
          {busy ? '…' : 'Run'}
        </button>
      </form>

      {result && (
        <pre className="result">{JSON.stringify(result, null, 2)}</pre>
      )}
      {queryError && <p className="error">{queryError}</p>}
    </div>
  );
}
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';

async function loadRuntimeConfig() {
  if (window.CONNECTS_CONFIG) return;
  try {
    const res = await fetch('/config.json');
    if (res.ok) window.CONNECTS_CONFIG = await res.json();
  } catch {
    // dev mode: fall back to import.meta.env values
  }
}

loadRuntimeConfig().then(() => {
  createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
});
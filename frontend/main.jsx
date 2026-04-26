import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import './mock-api.js';
import { App } from './app.jsx';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

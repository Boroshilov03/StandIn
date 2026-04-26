import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import './mock-api.js';
import { App } from './app.jsx';
import { LandingPage } from './landing.jsx';

function Root() {
  const [screen, setScreen] = useState('landing'); // 'landing' | 'app'
  if (screen === 'app') return <App onBackToLanding={() => setScreen('landing')} />;
  return <LandingPage onEnterDashboard={() => setScreen('app')} />;
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);

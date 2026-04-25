// StandIn — App shell: nav, health bar, route switcher, tweaks integration.

function HealthBar({ route, setRoute, counts }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick(x => x + 1), 5000);
    return () => clearInterval(t);
  }, []);
  const agents = window.MOCK_API.healthAgents();
  const state = window.MOCK_API.healthState();
  const source = window.MOCK_API.getSource();

  const tabs = [
    { id: 'attention', label: 'Attention',     count: counts.attention },
    { id: 'graph',     label: 'Team graph',    count: counts.graph },
    { id: 'monitor',   label: 'Orchestration', count: counts.feed },
  ];

  return (
    <header className="healthbar" data-screen-label="Top rail">
      <div className="brand">
        <div className="brand-mark"/>
        StandIn
        <small>NovaLoop</small>
      </div>
      <nav className="healthbar-nav" aria-label="Primary">
        {tabs.map(t => (
          <button key={t.id}
                  className={`nav-tab ${route === t.id ? 'active' : ''}`}
                  onClick={() => setRoute(t.id)}
                  aria-current={route === t.id ? 'page' : undefined}>
            {t.label}
            <span className="count tabular">{t.count}</span>
          </button>
        ))}
      </nav>
      <div className="healthbar-pills">
        {agents.map(a => {
          const st = state[a.id] || { online: true };
          return (
            <div key={a.id} className={`health-pill ${st.online ? '' : 'down'}`} title={`${a.name} :${a.port}`}>
              <span className="dot"/>
              <span>{a.name}</span>
              <span className="meta">
                <span>:{a.port}</span>
                <b className={st.Gemini ? '' : 'off'}>G</b>
                <b className={st.MongoDB ? '' : 'off'}>M</b>
              </span>
            </div>
          );
        })}
      </div>
      <div className="healthbar-spacer"/>
      <div className={`healthbar-source ${source === 'mongodb' ? 'live' : 'demo'}`}>
        {source === 'mongodb' ? 'live · mongodb' : 'demo · hardcoded'}
      </div>
    </header>
  );
}

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "showStubsOnly": false,
  "compact": false,
  "showHistoricalDown": false,
  "demoMode": false,
  "simulateTrace": "none"
}/*EDITMODE-END*/;

function App() {
  const [route, setRoute] = useState('attention');
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [activeTrace, setActiveTrace] = useState(null);
  const [openNode, setOpenNode] = useState(null);

  // Apply tweaks to mock API
  useEffect(() => {
    window.MOCK_API.setHealth('historical', { online: !tweaks.showHistoricalDown });
    window.MOCK_API.setSource(tweaks.demoMode ? 'hardcoded' : 'mongodb');
  }, [tweaks.showHistoricalDown, tweaks.demoMode]);

  // Body class for compact mode
  useEffect(() => {
    document.body.style.fontSize = tweaks.compact ? '13px' : '14px';
  }, [tweaks.compact]);

  // Simulated trace
  useEffect(() => {
    if (tweaks.simulateTrace && tweaks.simulateTrace !== 'none') {
      setActiveTrace(tweaks.simulateTrace);
      const t = setTimeout(() => setActiveTrace(null), 2400);
      return () => clearTimeout(t);
    }
  }, [tweaks.simulateTrace]);

  // Push a synthetic feed entry on trace simulate
  function activateTrace(which) {
    setActiveTrace(which);
    setTimeout(() => setActiveTrace(null), 2400);
  }

  // ESC closes graph selection
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') {
        // Tell graph to clear via a custom event
        window.dispatchEvent(new CustomEvent('standin-deselect'));
      }
      if (e.key === '1') setRoute('attention');
      if (e.key === '2') setRoute('graph');
      if (e.key === '3') setRoute('monitor');
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const counts = {
    attention: window.MOCK_API.listApprovals().length,
    graph:     window.MOCK_API.listUsers().length,
    feed:      window.MOCK_API.listFeed().length,
  };

  return (
    <div className="app">
      <HealthBar route={route} setRoute={setRoute} counts={counts}/>
      <div className="body">
        <main className="main" data-screen-label={`Route ${route}`}>
          {route === 'attention' && <AttentionBoard tweaks={{ activateTrace }}/>}
          {route === 'graph'     && <TeamGraph tweaks={{ openNode, clearOpenNode: () => setOpenNode(null) }}/>}
          {route === 'monitor'   && <OrchestrationMonitor activeTrace={activeTrace}/>}
        </main>
      </div>

      <TweaksPanel title="Tweaks">
        <TweakSection label="View">
          <TweakToggle label="Compact density" value={tweaks.compact} onChange={v => setTweak('compact', v)}/>
        </TweakSection>
        <TweakSection label="Backend simulation">
          <TweakToggle label="Demo data (hardcoded)" value={tweaks.demoMode} onChange={v => setTweak('demoMode', v)}/>
          <TweakToggle label="Historical down" value={tweaks.showHistoricalDown} onChange={v => setTweak('showHistoricalDown', v)}/>
        </TweakSection>
        <TweakSection label="Trace simulation">
          <TweakRadio
            label="Highlight pipeline path"
            value={tweaks.simulateTrace}
            onChange={v => setTweak('simulateTrace', v)}
            options={[
              { label: 'None',       value: 'none' },
              { label: 'Status',     value: 'status' },
              { label: 'Historical', value: 'historical' },
              { label: 'Action',     value: 'perform' },
            ]}
          />
          <TweakButton label="Open Orchestration Monitor" onClick={() => setRoute('monitor')}/>
        </TweakSection>
        <TweakSection label="Quick jumps">
          <TweakButton label="Inspect Derek (NOVA-142 owner)" onClick={() => { setRoute('graph'); setOpenNode('derek.vasquez'); }}/>
          <TweakButton label="Inspect Priya (Design)" onClick={() => { setRoute('graph'); setOpenNode('priya.mehta'); }}/>
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);

// StandIn — App shell: nav, health bar, route switcher, tweaks integration.

const NOTIF_KIND_META = {
  'conversation.resolved': { icon: '✓', tone: 'tone-success', label: 'Resolved' },
  'meeting.created':       { icon: '📅', tone: 'tone-info',    label: 'Meeting' },
  'action.executed':       { icon: '⚡', tone: 'tone-success', label: 'Action' },
  'action.failed':         { icon: '⚠', tone: 'tone-warn',    label: 'Failed' },
  'action.rejected':       { icon: '✕', tone: 'tone-muted',   label: 'Rejected' },
  'escalation.opened':     { icon: '!',  tone: 'tone-critical', label: 'Escalation' },
};

function _notifMeta(kind) {
  return NOTIF_KIND_META[kind] || { icon: '•', tone: 'tone-info', label: 'Update' };
}

function _fmtNotifTime(ts) {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    const diffMs = Date.now() - d.getTime();
    const sec = Math.floor(diffMs / 1000);
    if (sec < 60) return `${sec}s ago`;
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    return d.toLocaleDateString();
  } catch (_) { return ''; }
}

function NotificationToast({ notif, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 5200);
    return () => clearTimeout(t);
  }, [notif?.id]);
  if (!notif) return null;
  const meta = _notifMeta(notif.kind);
  return (
    <div className={`notif-toast ${meta.tone}`} role="status" onClick={onDismiss}>
      <span className="notif-toast-icon">{meta.icon}</span>
      <div className="notif-toast-body">
        <div className="notif-toast-title">{notif.title}</div>
        <div className="notif-toast-text">{notif.body}</div>
      </div>
    </div>
  );
}

function NotificationBell() {
  const [items,   setItems]   = useState(() => window.MOCK_API.listNotifications());
  const [unread,  setUnread]  = useState(() => window.MOCK_API.unreadNotifications());
  const [open,    setOpen]    = useState(false);
  const [toasts,  setToasts]  = useState([]);
  const ref = useRef(null);

  useEffect(() => {
    const off = window.MOCK_API.onNotifications((n, u, justArrived) => {
      setItems(n);
      setUnread(u);
      if (justArrived && justArrived.length > 0) {
        // Show up to 3 newest as toasts.
        setToasts(prev => [...justArrived.slice(0, 3), ...prev].slice(0, 3));
      }
    });
    return off;
  }, []);

  useEffect(() => {
    if (!open) return;
    function onClick(e) {
      if (!ref.current) return;
      if (ref.current.contains(e.target)) return;
      // Dropdown is portaled to body — exclude it from outside-click detection.
      if (e.target.closest && e.target.closest('.notif-dropdown')) return;
      setOpen(false);
    }
    function onKey(e) { if (e.key === 'Escape') setOpen(false); }
    window.addEventListener('mousedown', onClick);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onClick);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  function dismissToast(id) {
    setToasts(prev => prev.filter(t => t.id !== id));
  }

  function handleItemClick(n) {
    if (!n.read) window.MOCK_API.markNotificationsRead([n.id]);
  }

  function handleMarkAll() {
    window.MOCK_API.markAllNotificationsRead();
  }

  return (
    <>
      <div className="notif-bell-wrap" ref={ref}>
        <button
          className={`notif-bell ${unread > 0 ? 'has-unread' : ''}`}
          onClick={() => setOpen(o => !o)}
          aria-label={`Notifications${unread > 0 ? ` (${unread} unread)` : ''}`}
          aria-expanded={open}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
          {unread > 0 && <span className="notif-badge tabular">{unread > 99 ? '99+' : unread}</span>}
        </button>
        {open && ReactDOM.createPortal(
          <div className="notif-dropdown" role="dialog" aria-label="Notifications" ref={(el) => { if (el) el.dataset.portal = '1'; }}>
            <div className="notif-dropdown-head">
              <span className="notif-dropdown-title">Activity</span>
              {unread > 0 && (
                <button className="notif-mark-all" onClick={handleMarkAll}>Mark all read</button>
              )}
            </div>
            <div className="notif-dropdown-list">
              {items.length === 0 && (
                <div className="notif-empty">No notifications yet.</div>
              )}
              {items.map(n => {
                const meta = _notifMeta(n.kind);
                return (
                  <div
                    key={n.id}
                    className={`notif-item ${meta.tone} ${n.read ? '' : 'is-unread'}`}
                    onClick={() => handleItemClick(n)}
                  >
                    <span className="notif-item-icon">{meta.icon}</span>
                    <div className="notif-item-body">
                      <div className="notif-item-row">
                        <span className="notif-item-title">{n.title}</span>
                        <span className="notif-item-time">{_fmtNotifTime(n.ts)}</span>
                      </div>
                      <div className="notif-item-text">{n.body}</div>
                      <div className="notif-item-meta">
                        <span className={`notif-item-kind ${meta.tone}`}>{meta.label}</span>
                        {n.team && <span className="notif-item-tag">{n.team}</span>}
                        {n.owner && <span className="notif-item-tag muted">{n.owner}</span>}
                      </div>
                    </div>
                    {!n.read && <span className="notif-item-dot" aria-label="unread"/>}
                  </div>
                );
              })}
            </div>
          </div>,
          document.body
        )}
      </div>
      {!open && (
        <div className="notif-toast-stack" aria-live="polite">
          {toasts.map(t => (
            <NotificationToast key={t.id} notif={t} onDismiss={() => dismissToast(t.id)}/>
          ))}
        </div>
      )}
    </>
  );
}

function HealthBar({ route, setRoute, counts }) {
  useEffect(() => {
    const t = setInterval(() => window.MOCK_API.healthAgents(), 8000);
    return () => clearInterval(t);
  }, []);
  const agents = window.MOCK_API.healthAgents();
  const state  = window.MOCK_API.healthState();
  const source = window.MOCK_API.getSource();

  const tabs = [
    { id: 'attention', label: 'Attention',     count: counts.attention, kbd: '1' },
    { id: 'graph',     label: 'Team graph',    count: counts.graph,     kbd: '2' },
    { id: 'monitor',   label: 'Orchestration', count: counts.feed,      kbd: '3' },
  ];

  const offlineNames = agents.filter(a => !(state[a.id]?.online ?? true)).map(a => a.name);
  const allOnline    = offlineNames.length === 0;
  const isLive       = source === 'mongodb';

  let statusLabel, statusClass;
  if (!allOnline) {
    statusLabel = `${offlineNames.length} offline`;
    statusClass = 'degraded';
  } else if (isLive) {
    statusLabel = 'Live';
    statusClass = 'online';
  } else {
    statusLabel = 'Demo';
    statusClass = 'demo';
  }

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
            {t.count > 0 && <span className="count tabular">{t.count}</span>}
            <span className="nav-kbd">{t.kbd}</span>
          </button>
        ))}
      </nav>
      <div className="healthbar-spacer"/>
      <NotificationBell/>
      {statusClass !== 'demo' && (
        <div
          className={`system-status ${statusClass}`}
          title={allOnline ? `All agents online · ${source}` : `Offline: ${offlineNames.join(', ')}`}
        >
          <span className="dot"/>
          {statusLabel}
        </div>
      )}
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
          {/* AttentionBoard stays mounted so async query state survives the Orchestration redirect */}
          <div style={{ display: route === 'attention' ? 'contents' : 'none' }}>
            <AttentionBoard tweaks={{ activateTrace, navigateToMonitor: () => setRoute('monitor'), navigateToAttention: () => setRoute('attention') }}/>
          </div>
          {route === 'graph'   && <TeamGraph tweaks={{ openNode, clearOpenNode: () => setOpenNode(null) }}/>}
          {route === 'monitor' && <OrchestrationMonitor activeTrace={activeTrace}/>}
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

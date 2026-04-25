// StandIn — Orchestration Monitor.

const TRACE_ACCENTS = {
  status:     { color: 'var(--eng)',    bg: 'oklch(0.30 0.10 245)' },
  historical: { color: 'var(--design)', bg: 'oklch(0.30 0.10 305)' },
  perform:    { color: 'var(--gtm)',    bg: 'oklch(0.30 0.10 55)'  },
};

function OrchestrationMonitor({ activeTrace }) {
  const [monTab, setMonTab] = useState('flow');
  const [feed, setFeed]     = useState(() => window.MOCK_API.listFeed());

  useEffect(() => {
    const t = setInterval(() => setFeed(window.MOCK_API.listFeed()), 1500);
    return () => clearInterval(t);
  }, []);

  const accent      = TRACE_ACCENTS[activeTrace] || null;
  const accentStyle = accent ? { '--accent': accent.color, '--accent-bg': accent.bg } : {};

  return (
    <div className="monitor-outer">
      {/* Tab bar */}
      <div className="monitor-tabbar">
        <button
          className={`monitor-tab ${monTab === 'flow' ? 'active' : ''}`}
          onClick={() => setMonTab('flow')}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <circle cx="6.5" cy="6.5" r="2.5" fill="currentColor" opacity="0.7"/>
            <circle cx="6.5" cy="6.5" r="5.5" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2" opacity="0.5"/>
          </svg>
          Agent graph
        </button>
        <button
          className={`monitor-tab ${monTab === 'pipeline' ? 'active' : ''}`}
          onClick={() => setMonTab('pipeline')}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <rect x="1" y="1" width="11" height="3" rx="1" fill="currentColor" opacity="0.6"/>
            <rect x="4" y="6" width="8" height="3" rx="1" fill="currentColor" opacity="0.6"/>
            <line x1="2.5" y1="4" x2="2.5" y2="6" stroke="currentColor" strokeWidth="1" opacity="0.5"/>
          </svg>
          Pipeline trace
        </button>
      </div>

      {/* Agent graph tab */}
      {monTab === 'flow' && <AgentFlowGraph activeTrace={activeTrace}/>}

      {/* Pipeline trace tab */}
      {monTab === 'pipeline' && (
        <div className="monitor" style={accentStyle}>
          <div className="flow-col">
            <h2>Orchestration flow</h2>
            <p>Live request pipeline. The active path glows while a trace is in flight.</p>

            <div className="flow">
              <div className={`flow-node ${activeTrace ? 'active' : ''}`}>
                User <span className="sub">via ASI:One</span>
              </div>
              <div className={`flow-arrow ${activeTrace ? 'active' : ''}`}/>
              <div className={`flow-node ${activeTrace ? 'active' : ''}`}>
                Orchestrator <span className="sub">port 8000 · gemini-2.5-flash</span>
              </div>
              <div className={`flow-arrow ${activeTrace ? 'active' : ''}`}/>
              <div className={`flow-node ${activeTrace ? 'active' : ''}`}>
                Intent Classification <span className="sub">Gemini · 5 intents</span>
              </div>
              <div className={`flow-arrow ${activeTrace ? 'active' : ''}`}/>
              <div className="flow-branches">
                <FlowBranch
                  tag="Intent 1, 2, 5"
                  agent="Status Agent"
                  port="8007"
                  tools={[
                    { name: 'Gather',     stub: false },
                    { name: 'Synthesise', stub: false },
                    { name: 'Contradict', stub: false },
                    { name: 'Passports',  stub: false },
                  ]}
                  active={activeTrace === 'status'}
                />
                <FlowBranch
                  tag="Intent 4"
                  agent="Historical Agent"
                  port="8009"
                  tools={[
                    { name: 'Tier 1 — Vector',  stub: false },
                    { name: 'Tier 2 — Keyword', stub: false },
                    { name: 'Synthesise',        stub: false },
                  ]}
                  active={activeTrace === 'historical'}
                />
                <FlowBranch
                  tag="Intent 3"
                  agent="Perform Action"
                  port="8008"
                  tools={[
                    { name: 'Approval Gate?', stub: false },
                    { name: 'Execute',        stub: true  },
                    { name: 'Stub fallback',  stub: true  },
                  ]}
                  active={activeTrace === 'perform'}
                />
              </div>
            </div>
          </div>

          <div className="feed-col">
            <h2>Tool call feed</h2>
            <p>Live log of recent tool calls and actions. Polled every 1.5 s.</p>
            <div className="feed-list">
              <div className="feed-thead">
                <span>time</span>
                <span>agent</span>
                <span>tool</span>
                <span>status</span>
                <span>detail</span>
              </div>
              {feed.map((row, i) => (
                <FeedRow key={i + row.ts} row={row}/>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FlowBranch({ tag, agent, port, tools, active }) {
  return (
    <div className={`flow-branch ${active ? 'active' : ''}`}>
      <div className="head">{tag}</div>
      <div className="agent">
        {agent}
        <span style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 10.5, fontWeight: 400 }}>
          :{port}
        </span>
      </div>
      <div className="flow-tools">
        {tools.map(t => (
          <div key={t.name} className={`flow-tool ${t.stub ? 'stub' : ''} ${active ? 'active' : ''}`}>
            <span className="dot"/> {t.name}
          </div>
        ))}
      </div>
    </div>
  );
}

function FeedRow({ row }) {
  const cls = ['feed-row'];
  if (row._new) cls.push('is-new');
  const s = row.status ? row.status.toLowerCase() : '';
  if (s) cls.push(`status-${s}`);
  return (
    <div className={cls.join(' ')}>
      <span className="ts">{timeOnly(row.ts)}</span>
      <span className="agent">{row.agent}</span>
      <span className="tool">→ {row.tool}</span>
      <span><StatusPill status={s}/></span>
      <span className="meta">
        {row.stub && <span className="status-pill stub" style={{ marginRight: 6 }}><span className="dot"/>stub</span>}
        {row.meta}
      </span>
    </div>
  );
}

Object.assign(window, { OrchestrationMonitor });

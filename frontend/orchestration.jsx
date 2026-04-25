// StandIn — Orchestration Monitor.

const TRACE_ACCENTS = {
  status:     { color: 'var(--eng)',     bg: 'oklch(0.30 0.10 245)' },
  historical: { color: 'var(--design)',  bg: 'oklch(0.30 0.10 305)' },
  perform:    { color: 'var(--gtm)',     bg: 'oklch(0.30 0.10 55)'  },
};

function OrchestrationMonitor({ activeTrace }) {
  const [feed, setFeed] = useState(() => window.MOCK_API.listFeed());

  useEffect(() => {
    const t = setInterval(() => setFeed(window.MOCK_API.listFeed()), 1500);
    return () => clearInterval(t);
  }, []);

  const accent = TRACE_ACCENTS[activeTrace] || null;
  const accentStyle = accent ? { '--accent': accent.color, '--accent-bg': accent.bg } : {};

  return (
    <div className="monitor" style={accentStyle}>
      <div className="flow-col">
        <h2>Orchestration flow</h2>
        <p>Live request pipeline. The active path glows in the requesting user's team color while a trace is in flight.</p>

        <div className="flow">
          <div className={`flow-node ${activeTrace ? 'active' : ''}`}>
            User <span className="sub">via ASI:One</span>
          </div>
          <div className={`flow-arrow ${activeTrace ? 'active' : ''}`}/>
          <div className={`flow-node ${activeTrace ? 'active' : ''}`}>
            Orchestrator <span className="sub">port 8000 · gemini-2.0-flash</span>
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
                { name: 'Synthesise',       stub: false },
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
        <p>Live log of recent tool calls and actions. Polled every 1.5 s.</p>
        <div className="feed-list">
          {feed.map((row, i) => (
            <FeedRow key={i + row.ts} row={row} />
          ))}
        </div>
      </div>
    </div>
  );
}

function FlowBranch({ tag, agent, port, tools, active }) {
  return (
    <div className={`flow-branch ${active ? 'active' : ''}`}>
      <div className="head">{tag}</div>
      <div className="agent">{agent} <span style={{color:'var(--fg-3)', fontFamily:'var(--font-mono)', fontSize: 10.5, fontWeight:400}}>:{port}</span></div>
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
  return (
    <div className={cls.join(' ')}>
      <span className="ts">{timeOnly(row.ts)}</span>
      <span className="agent">{row.agent}</span>
      <span className="tool">→ {row.tool}</span>
      <span><StatusPill status={row.status.toLowerCase()} /></span>
      <span className="meta">
        {row.stub && <span className="status-pill stub" style={{marginRight:6}}><span className="dot"/>stub</span>}
        {row.meta}
      </span>
    </div>
  );
}

Object.assign(window, { OrchestrationMonitor });

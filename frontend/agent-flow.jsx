// StandIn — Agent Flow: animated node-based orchestration observer.
// Hardcoded scenarios — swap SCENARIOS data once live event stream is available.

const AF_NW = 144, AF_NH = 52, AF_NHW = AF_NW / 2, AF_NHH = AF_NH / 2;

const AF_NODES = {
  user:       { cx: 400, cy: 52,  label: 'User / ASI:One',   sub: 'entry point',   c: 'oklch(0.62 0.008 60)' },
  orch:       { cx: 400, cy: 186, label: 'Orchestrator',     sub: 'port 8000',     c: 'oklch(0.72 0.14 245)' },
  status:     { cx: 163, cy: 350, label: 'Status Agent',     sub: 'port 8007',     c: 'oklch(0.72 0.16 245)' },
  historical: { cx: 400, cy: 350, label: 'Historical Agent', sub: 'port 8009',     c: 'oklch(0.72 0.18 305)' },
  perform:    { cx: 637, cy: 350, label: 'Perform Action',   sub: 'port 8008',     c: 'oklch(0.74 0.16 55)' },
  watchdog:   { cx: 90,  cy: 226, label: 'Watchdog',         sub: 'port 8010',     c: 'oklch(0.74 0.16 145)' },
};

const AF_EDGES = [
  { id: 'user-orch',        from: 'user',     to: 'orch',       d: 'M 400 78 L 400 160' },
  { id: 'orch-status',      from: 'orch',     to: 'status',     d: 'M 368 212 C 338 268 228 308 163 324' },
  { id: 'orch-historical',  from: 'orch',     to: 'historical', d: 'M 400 212 L 400 324' },
  { id: 'orch-perform',     from: 'orch',     to: 'perform',    d: 'M 432 212 C 462 268 572 308 637 324' },
  { id: 'watchdog-status',  from: 'watchdog', to: 'status',     d: 'M 161 227 C 163 272 163 302 163 324' },
  { id: 'watchdog-perform', from: 'watchdog', to: 'perform',    d: 'M 162 236 C 380 162 546 260 637 324' },
];

const AF_SCENARIOS = [
  {
    id: 'status', label: 'Status Query', c: 'oklch(0.72 0.16 245)',
    steps: [
      {
        edge: 'user-orch', dir: 'fwd', active: ['user', 'orch'],
        model: 'ChatMessage',
        payload: '"What is Launch Alpha readiness right now?"',
        desc: 'User query received via ASI:One. Orchestrator classifies intent using Gemini → intent 1 (status query).',
      },
      {
        edge: 'orch-status', dir: 'fwd', active: ['orch', 'status'],
        model: 'FullBriefRequest',
        payload: '{ user_email: "priya@novaloop.io", topic: "Launch Alpha", roles: null, session_id: null }',
        desc: 'Routed to Status Agent. All four roles (Eng, Design, GTM, Product) queried in parallel via Gemini synthesis.',
      },
      {
        edge: 'orch-status', dir: 'rev', active: ['status', 'orch'],
        model: 'FullBriefResponse',
        payload: '{ escalation_required: true, contradictions: ["Design=ready, Eng=blocked on NOVA-142"], overall_confidence: 0.61 }',
        desc: 'Brief returned with contradiction detected. Evidence Passports generated for 2 high-risk claims. Escalation flag raised.',
      },
      {
        edge: 'user-orch', dir: 'rev', active: ['orch', 'user'],
        model: 'ChatMessage',
        payload: '"🚨 Escalation required: Design says ready, Engineering is blocked. Recommend 15-min sync."',
        desc: 'Orchestrator formats response and delivers to user via ASI:One chat.',
      },
    ],
  },
  {
    id: 'history', label: 'History Query', c: 'oklch(0.72 0.18 305)',
    steps: [
      {
        edge: 'user-orch', dir: 'fwd', active: ['user', 'orch'],
        model: 'ChatMessage',
        payload: '"What was decided in last week\'s launch sync?"',
        desc: 'History query received. Orchestrator classifies as intent 4 → routes to Historical Agent.',
      },
      {
        edge: 'orch-historical', dir: 'fwd', active: ['orch', 'historical'],
        model: 'RAGRequest',
        payload: '{ question: "launch sync decisions", top_k: 5, role_filter: null }',
        desc: 'RAG pipeline executes: Tier 1 Atlas vector search → Tier 2 BM25 keyword → Tier 3 Gemini synthesis fallback.',
      },
      {
        edge: 'orch-historical', dir: 'rev', active: ['historical', 'orch'],
        model: 'RAGResponse',
        payload: '{ answer: "...", source_ids: ["meeting-2026-04-18"], confidence: 0.88, retrieval_method: "vector_search" }',
        desc: 'Tier-1 vector search hit. Answer synthesised from meeting notes with source attribution. confidence=0.88.',
      },
      {
        edge: 'user-orch', dir: 'rev', active: ['orch', 'user'],
        model: 'ChatMessage',
        payload: '"On 2026-04-18 the team agreed to migrate to API v2 before launch. Owner: Derek Vasquez."',
        desc: 'Historical answer with cited source delivered to user.',
      },
    ],
  },
  {
    id: 'action', label: 'Action Request', c: 'oklch(0.74 0.16 55)',
    steps: [
      {
        edge: 'user-orch', dir: 'fwd', active: ['user', 'orch'],
        model: 'ChatMessage',
        payload: '"Schedule a sync between Design and Engineering today"',
        desc: 'Action intent detected. Orchestrator extracts action_type=schedule_meeting and involved parties.',
      },
      {
        edge: 'orch-perform', dir: 'fwd', active: ['orch', 'perform'],
        model: 'ActionRequest',
        payload: '{ action_type: "schedule_meeting", priority: "urgent", risk: "high", title: "Design×Eng escalation sync" }',
        desc: 'Sent to Perform Action. schedule_meeting requires human approval — written to pending_approvals collection.',
      },
      {
        edge: 'orch-perform', dir: 'rev', active: ['perform', 'orch'],
        model: 'ActionResponse',
        payload: '{ success: true, stub: true, action_id: "act_7f3a…", pending_approval: true }',
        desc: 'Action queued. stub=true: MCP Calendar not yet connected. Approval card created on Attention Board.',
      },
      {
        edge: 'user-orch', dir: 'rev', active: ['orch', 'user'],
        model: 'ChatMessage',
        payload: '"⏳ Meeting request queued. Awaiting your approval on the StandIn dashboard."',
        desc: 'User notified. Approval card with payload preview appears under Attention Board.',
      },
    ],
  },
  {
    id: 'watchdog', label: 'Watchdog Poll', c: 'oklch(0.74 0.16 145)',
    steps: [
      {
        edge: 'watchdog-status', dir: 'fwd', active: ['watchdog', 'status'],
        model: 'FullBriefRequest',
        payload: '{ user_email: "watchdog@standin.ai", session_id: "wdg_9c1…" }',
        desc: 'Watchdog fires scheduled poll to Status Agent (every 30 min). session_id threads memory for delta detection.',
      },
      {
        edge: 'watchdog-status', dir: 'rev', active: ['status', 'watchdog'],
        model: 'FullBriefResponse',
        payload: '{ delta_claims: ["Eng confidence: 0.72→0.41", "New blocker: NOVA-149"], overall_confidence: 0.41 }',
        desc: 'Status change detected via conversation history diff. delta_claims populated with two new Engineering blockers.',
      },
      {
        edge: 'watchdog-perform', dir: 'fwd', active: ['watchdog', 'perform'],
        model: 'ActionRequest',
        payload: '{ action_type: "draft_slack", payload: { channel: "#eng-leads", text: "⚠ Eng confidence dropped to 0.41" } }',
        desc: 'Watchdog fires draft_slack. No approval required — drafts are non-destructive.',
      },
      {
        edge: 'watchdog-perform', dir: 'rev', active: ['perform', 'watchdog'],
        model: 'ActionResponse',
        payload: '{ success: true, stub: true }',
        desc: 'Slack draft created (stubbed — MCP Slack pending). Alert surfaced in Orchestration feed.',
      },
    ],
  },
];

function AgentFlowGraph({ activeTrace }) {
  const [scIdx, setScIdx]     = useState(0);
  const [stIdx, setStIdx]     = useState(0);
  const [running, setRunning] = useState(true);
  const scIdxRef = React.useRef(scIdx);

  // Keep ref in sync so interval closure can read latest scIdx
  useEffect(() => { scIdxRef.current = scIdx; }, [scIdx]);

  const scenario = AF_SCENARIOS[scIdx];
  const step     = scenario.steps[stIdx];
  const edgeDef  = AF_EDGES.find(e => e.id === step.edge);
  const activeNodes = new Set(step.active || []);
  const isRev = step.dir === 'rev';

  // Auto-advance steps → scenarios
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => {
      setStIdx(prev => {
        const sc = scIdxRef.current;
        if (prev + 1 >= AF_SCENARIOS[sc].steps.length) {
          setScIdx(s => (s + 1) % AF_SCENARIOS.length);
          return 0;
        }
        return prev + 1;
      });
    }, 2400);
    return () => clearInterval(t);
  }, [running]);

  // Sync to activeTrace from parent tweaks panel
  useEffect(() => {
    if (!activeTrace || activeTrace === 'none') return;
    const idx = AF_SCENARIOS.findIndex(s => s.id === activeTrace);
    if (idx >= 0) { setScIdx(idx); setStIdx(0); }
  }, [activeTrace]);

  function selectScenario(i) { setScIdx(i); setStIdx(0); }

  return (
    <div className="af-wrap">
      {/* Toolbar */}
      <div className="af-toolbar">
        <div className="btn-group">
          {AF_SCENARIOS.map((sc, i) => (
            <button key={sc.id}
              className={scIdx === i ? 'active' : ''}
              onClick={() => selectScenario(i)}
              style={scIdx === i ? { color: sc.c } : {}}>
              {sc.label}
            </button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <div className="af-legend">
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <svg width="20" height="2"><line x1="0" y1="1" x2="20" y2="1" stroke="oklch(0.280 0.010 60)" strokeWidth="1.5" strokeDasharray="4 4"/></svg>
            idle edge
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <svg width="20" height="8"><circle cx="10" cy="4" r="4" fill={scenario.c}/></svg>
            message packet
          </span>
        </div>
        <button className="btn ghost af-play-btn"
          onClick={() => setRunning(r => !r)}>
          {running
            ? <svg width="12" height="12" viewBox="0 0 12 12"><rect x="1" y="1" width="4" height="10" rx="1" fill="currentColor"/><rect x="7" y="1" width="4" height="10" rx="1" fill="currentColor"/></svg>
            : <svg width="12" height="12" viewBox="0 0 12 12"><polygon points="1,0 12,6 1,12" fill="currentColor"/></svg>
          }
          {running ? 'Pause' : 'Play'}
        </button>
      </div>

      {/* SVG Graph */}
      <div className="af-stage">
        <svg viewBox="0 0 800 415" className="af-svg" preserveAspectRatio="xMidYMid meet">
          <defs>
            <pattern id="af-grid" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
              <path d="M 32 0 L 0 0 0 32" fill="none"
                stroke="oklch(0.250 0.009 60)" strokeWidth="0.4"/>
            </pattern>
            {/* Path refs for animateMotion */}
            {AF_EDGES.map(e => (
              <path key={`dp-${e.id}`} id={`afp-${e.id}`} d={e.d}/>
            ))}
          </defs>

          {/* Background grid */}
          <rect width="800" height="415" fill="url(#af-grid)" opacity="0.35"/>

          {/* Dim static edges */}
          {AF_EDGES.map(e => (
            <path key={`bg-${e.id}`} d={e.d} fill="none"
              stroke="oklch(0.285 0.010 60)" strokeWidth="1.5"
              strokeDasharray="5 5"/>
          ))}

          {/* Active edge: glow + packet */}
          {edgeDef && (
            <g key={`${step.edge}-${step.dir}-${stIdx}-${scIdx}`}>
              {/* Wide glow */}
              <path d={edgeDef.d} fill="none"
                stroke={scenario.c} strokeWidth="8" opacity="0.12"
                style={{ filter: 'blur(4px)' }}/>
              {/* Crisp lit line */}
              <path d={edgeDef.d} fill="none"
                stroke={scenario.c} strokeWidth="2" opacity="0.88"
                strokeLinecap="round"/>

              {/* Trailing ring (pulses around the packet) */}
              <circle r="5" fill="none" stroke={scenario.c} strokeWidth="1.5">
                <animateMotion dur="1.15s" repeatCount="indefinite"
                  keyPoints={isRev ? '1;0' : '0;1'} keyTimes="0;1" calcMode="linear">
                  <mpath href={`#afp-${step.edge}`}/>
                </animateMotion>
                <animate attributeName="r" dur="1.15s" repeatCount="indefinite"
                  values="4;16;4" keyTimes="0;0.35;1"/>
                <animate attributeName="opacity" dur="1.15s" repeatCount="indefinite"
                  values="0;0.55;0" keyTimes="0;0.25;1"/>
              </circle>

              {/* Main packet dot */}
              <circle r="6" fill={scenario.c} opacity="0.95"
                style={{ filter: `drop-shadow(0 0 7px ${scenario.c})` }}>
                <animateMotion dur="1.15s" repeatCount="indefinite"
                  keyPoints={isRev ? '1;0' : '0;1'} keyTimes="0;1" calcMode="linear">
                  <mpath href={`#afp-${step.edge}`}/>
                </animateMotion>
              </circle>
            </g>
          )}

          {/* Nodes */}
          {Object.entries(AF_NODES).map(([id, n]) => {
            const isActive     = activeNodes.has(id);
            const isProcessing = step.active && step.active.includes(id);
            const nodeColor    = isActive ? scenario.c : n.c;
            return (
              <g key={id} className="af-node-g">
                {/* Glow halo */}
                {isActive && (
                  <rect
                    x={n.cx - AF_NHW - 7} y={n.cy - AF_NHH - 7}
                    width={AF_NW + 14} height={AF_NH + 14} rx="14"
                    fill={scenario.c} opacity="0.10"
                    style={{ filter: 'blur(9px)' }}/>
                )}

                {/* Card body */}
                <rect
                  x={n.cx - AF_NHW} y={n.cy - AF_NHH}
                  width={AF_NW} height={AF_NH} rx="8"
                  fill={isActive ? 'oklch(0.230 0.010 60)' : 'oklch(0.205 0.009 60)'}
                  stroke={isActive ? nodeColor : 'oklch(0.295 0.010 60)'}
                  strokeWidth={isActive ? 1.5 : 1}/>

                {/* Top accent strip */}
                <rect
                  x={n.cx - AF_NHW + 10} y={n.cy - AF_NHH}
                  width={AF_NW - 20} height={3} rx="1.5"
                  fill={nodeColor}
                  opacity={isActive ? 0.95 : 0.30}/>

                {/* Agent name */}
                <text x={n.cx} y={n.cy - 3}
                  textAnchor="middle"
                  fill={isActive ? 'oklch(0.97 0.004 60)' : 'oklch(0.78 0.006 60)'}
                  fontSize="12.5" fontWeight="600"
                  fontFamily="Geist, Inter, system-ui, sans-serif"
                  letterSpacing="-0.4">
                  {n.label}
                </text>

                {/* Sub / status line */}
                <text x={n.cx} y={n.cy + 15}
                  textAnchor="middle"
                  fill={isProcessing ? nodeColor : 'oklch(0.46 0.009 60)'}
                  fontSize="10" fontWeight={isProcessing ? '500' : '400'}
                  fontFamily="Geist Mono, JetBrains Mono, monospace">
                  {isProcessing ? '● processing…' : n.sub}
                </text>

                {/* Active indicator dot in corner */}
                {isActive && (
                  <circle cx={n.cx + AF_NHW - 10} cy={n.cy - AF_NHH + 10}
                    r="3.5" fill={scenario.c} opacity="0.9">
                    <animate attributeName="opacity" dur="1.2s" repeatCount="indefinite"
                      values="0.9;0.3;0.9"/>
                  </circle>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Step detail card */}
      <div className="af-detail">
        <div className="af-detail-left">
          <div className="af-detail-model" style={{ color: scenario.c }}>
            {step.dir === 'fwd' ? '→' : '←'} {step.model}
            <span className="af-edge-path">
              {step.dir === 'fwd'
                ? `${edgeDef?.from} → ${edgeDef?.to}`
                : `${edgeDef?.to} → ${edgeDef?.from}`}
            </span>
          </div>
          <div className="af-detail-payload">{step.payload}</div>
          <div className="af-detail-desc">{step.desc}</div>
        </div>
        <div className="af-detail-right">
          <div className="af-step-nav">
            {scenario.steps.map((_, i) => (
              <button key={i}
                className={`af-step-dot ${i === stIdx ? 'active' : ''}`}
                onClick={() => setStIdx(i)}
                style={i === stIdx ? { background: scenario.c, boxShadow: `0 0 6px ${scenario.c}` } : {}}/>
            ))}
          </div>
          <div className="af-step-count" style={{ color: scenario.c }}>
            step {stIdx + 1} / {scenario.steps.length}
          </div>
          <div className="af-scenario-label" style={{ color: scenario.c }}>
            {scenario.label}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AgentFlowGraph });

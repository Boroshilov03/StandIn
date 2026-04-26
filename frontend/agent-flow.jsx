// StandIn — Agent Flow: animated node-based orchestration observer.
// Hardcoded scenarios — swap SCENARIOS data once live event stream is available.

import React, { useEffect, useState } from 'react';

const AF_NW = 144, AF_NH = 52, AF_NHW = AF_NW / 2, AF_NHH = AF_NH / 2;

const AF_NODES = {
  user:       { cx: 400, cy: 52,  label: 'User / ASI:One',   sub: 'entry point',   c: 'oklch(0.62 0.008 60)' },
  orch:       { cx: 400, cy: 186, label: 'Orchestrator',     sub: 'port 8000',     c: 'oklch(0.72 0.14 245)' },
  status:     { cx: 163, cy: 320, label: 'Status Agent',     sub: 'port 8007',     c: 'oklch(0.72 0.16 245)' },
  historical: { cx: 400, cy: 320, label: 'Historical Agent', sub: 'port 8009',     c: 'oklch(0.72 0.18 305)' },
  perform:    { cx: 637, cy: 320, label: 'Perform Action',   sub: 'port 8008',     c: 'oklch(0.74 0.16 55)' },
  watchdog:   { cx: 90,  cy: 196, label: 'Watchdog',         sub: 'port 8010',     c: 'oklch(0.74 0.16 145)' },
};

// Tool nodes — children of agents. cx,cy place a small pill below parent agent.
const AF_TW = 92, AF_TH = 22;
const AF_TOOLS = {
  // Status agent tools (port 8007)
  'status.gather':     { parent: 'status',     cx: 70,  cy: 410, label: 'gather',     icon: '⤓' },
  'status.rag':        { parent: 'status',     cx: 70,  cy: 440, label: 'rag.search', icon: '🔍' },
  'status.synth':      { parent: 'status',     cx: 168, cy: 410, label: 'synthesise', icon: '✦' },
  'status.contradict': { parent: 'status',     cx: 168, cy: 440, label: 'contradict', icon: '⚡' },
  'status.passports':  { parent: 'status',     cx: 266, cy: 425, label: 'passports',  icon: '⬢' },
  // Historical agent tools (port 8009)
  'hist.vector':       { parent: 'historical', cx: 308, cy: 410, label: 'vector',     icon: '◇' },
  'hist.keyword':      { parent: 'historical', cx: 308, cy: 440, label: 'keyword',    icon: '⌕' },
  'hist.synth':        { parent: 'historical', cx: 405, cy: 425, label: 'synthesise', icon: '✦' },
  'hist.mongo':        { parent: 'historical', cx: 503, cy: 425, label: 'mongo.atlas',icon: '⬡' },
  // Perform Action tools (port 8008)
  'perf.approval':     { parent: 'perform',    cx: 545, cy: 425, label: 'approval',   icon: '🔒' },
  'perf.slack':        { parent: 'perform',    cx: 643, cy: 410, label: 'slack',      icon: '#' },
  'perf.jira':         { parent: 'perform',    cx: 643, cy: 440, label: 'jira',       icon: 'J' },
  'perf.calendar':     { parent: 'perform',    cx: 740, cy: 410, label: 'calendar',   icon: '📅' },
  'perf.gmail':        { parent: 'perform',    cx: 740, cy: 440, label: 'gmail',      icon: '✉' },
};

const AF_EDGES = [
  { id: 'user-orch',        from: 'user',     to: 'orch',       d: 'M 400 78 L 400 160' },
  { id: 'orch-status',      from: 'orch',     to: 'status',     d: 'M 368 212 C 338 240 228 280 163 294' },
  { id: 'orch-historical',  from: 'orch',     to: 'historical', d: 'M 400 212 L 400 294' },
  { id: 'orch-perform',     from: 'orch',     to: 'perform',    d: 'M 432 212 C 462 240 572 280 637 294' },
  { id: 'watchdog-status',  from: 'watchdog', to: 'status',     d: 'M 161 197 C 163 240 163 272 163 294' },
  { id: 'watchdog-perform', from: 'watchdog', to: 'perform',    d: 'M 162 206 C 380 132 546 230 637 294' },
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
        edge: 'orch-status', dir: 'fwd', active: ['status'],
        tools: ['status.gather', 'status.rag'],
        model: 'tool: gather()',
        payload: 'gather(roles=[Eng, Design, GTM, Product]) → slack + jira + rag.search',
        desc: 'Phase 1 — gather. Status Agent invokes gather tool: parallel async pulls from Slack, Jira, MongoDB RAG vector search across all four roles.',
      },
      {
        edge: 'orch-status', dir: 'fwd', active: ['status'],
        tools: ['status.synth'],
        model: 'tool: synthesise()',
        payload: 'gemini-2.5-flash · 4 parallel role syntheses · structured output',
        desc: 'Phase 2 — synthesise. Status Agent invokes Gemini once per role to summarise gathered evidence into structured RoleStatus objects.',
      },
      {
        edge: 'orch-status', dir: 'fwd', active: ['status'],
        tools: ['status.contradict', 'status.passports'],
        model: 'tool: contradict() + passports()',
        payload: 'rule_engine: Design=ready ⊥ Eng=blocked → escalation_required=true',
        desc: 'Phase 3+4 — contradict + passports. Rule engine detects Design/Eng conflict; Evidence Passports generated for both high-risk claims.',
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
    id: 'history', label: 'History Query (Fan-out)', c: 'oklch(0.72 0.18 305)',
    steps: [
      {
        edge: 'user-orch', dir: 'fwd', active: ['user', 'orch'],
        model: 'ChatMessage',
        payload: '"What blockers has Derek Vasquez faced?"',
        desc: 'History/entity query received. Orchestrator classifies as intent 4 → fan-out mode: fires Historical Agent AND Status Agent in parallel.',
      },
      {
        edge: 'orch-historical', dir: 'fwd', active: ['orch', 'historical'],
        model: 'RAGRequest',
        payload: '{ question: "Derek Vasquez blockers", top_k: 6, role_filter: null }',
        desc: 'Fan-out arm 1 → Historical Agent. MongoDB Atlas vector search on "Derek Vasquez blockers". Finds doc_derek_vasquez, doc_backend_ticket, NOVA-142.',
      },
      {
        edge: 'orch-historical', dir: 'fwd', active: ['historical'],
        tools: ['hist.vector', 'hist.mongo'],
        model: 'tool: tier1_vector()',
        payload: 'embed(question) · cosine k=6 · standin.documents',
        desc: 'Tier 1 — vector search. Historical Agent embeds the query (Gemini text-embedding-004) and runs MongoDB Atlas Vector Search.',
      },
      {
        edge: 'orch-historical', dir: 'fwd', active: ['historical'],
        tools: ['hist.synth'],
        model: 'tool: synthesise()',
        payload: 'gemini-2.5-flash + retrieved context → answer',
        desc: 'Synthesise tool runs Gemini over the retrieved docs to produce an answer with source_ids and confidence.',
      },
      {
        edge: 'orch-status', dir: 'fwd', active: ['orch', 'status'],
        tools: ['status.gather', 'status.rag', 'status.synth'],
        model: 'FullBriefRequest (parallel)',
        payload: '{ context: "Derek Vasquez blockers", roles: null, user_email: "…" }',
        desc: 'Fan-out arm 2 (parallel) → Status Agent. gather + rag.search + synthesise tools fire concurrently with the historical arm.',
      },
      {
        edge: 'orch-historical', dir: 'rev', active: ['historical', 'orch'],
        model: 'RAGResponse',
        payload: '{ answer: "Derek owns NOVA-142 (BLOCKED)…", source_ids: ["doc_derek_vasquez","doc_backend_ticket"], confidence: 0.88, retrieval_method: "vector_search" }',
        desc: 'Historical context arrives: Derek\'s profile, NOVA-142 details, API contract change. Orchestrator stores and waits for status arm.',
      },
      {
        edge: 'orch-status', dir: 'rev', active: ['status', 'orch'],
        model: 'FullBriefResponse (merge trigger)',
        payload: '{ escalation_required: true, contradictions: ["Design=ready, Eng=blocked on NOVA-142"], overall_confidence: 0.61 }',
        desc: 'Live status arrives. Both arms done → orchestrator merges: historical doc context prepended to live status summary.',
      },
      {
        edge: 'user-orch', dir: 'rev', active: ['orch', 'user'],
        model: 'ChatMessage (merged)',
        payload: '"Historical context: Derek owns NOVA-142 (BLOCKED, v2 API)…\\nCurrent live status: Engineering blocked, escalation required."',
        desc: 'Merged answer delivered: document history + live JIRA/Slack data combined into one response.',
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
        edge: 'orch-perform', dir: 'fwd', active: ['perform'],
        tools: ['perf.approval'],
        model: 'tool: approval_gate()',
        payload: 'risk=high · approval_required=true · queued in standin.pending_approvals',
        desc: 'Approval gate fires. Calendar tool execution is held until a human approves the action via the Attention Board.',
      },
      {
        edge: 'orch-perform', dir: 'fwd', active: ['perform'],
        tools: ['perf.calendar'],
        model: 'tool: calendar.schedule (deferred)',
        payload: 'mcp__claude_ai_Google_Calendar (stubbed) · attendees=[priya,derek,alice]',
        desc: 'Calendar MCP tool prepared (stub mode). Will execute on approve.',
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
        tools: ['perf.slack'],
        model: 'ActionRequest',
        payload: '{ action_type: "draft_slack", payload: { channel: "#eng-leads", text: "⚠ Eng confidence dropped to 0.41" } }',
        desc: 'Watchdog fires draft_slack. Slack MCP tool runs without approval — drafts are non-destructive.',
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

// Maps tweaks-panel activeTrace values to AF_SCENARIOS ids
const _ACCENT_TO_SC = { status: 'status', historical: 'history', perform: 'action' };

export function AgentFlowGraph({ activeTrace }) {
  const [scIdx, setScIdx]       = useState(0);
  const [stIdx, setStIdx]       = useState(0);
  const [running, setRunning]   = useState(true);
  const [liveTrace, setLiveTrace] = useState(null);
  const scIdxRef    = React.useRef(scIdx);
  const liveRef     = React.useRef(null);

  // Keep refs in sync
  useEffect(() => { scIdxRef.current = scIdx; }, [scIdx]);

  // Poll live trace every 250 ms
  useEffect(() => {
    const t = setInterval(() => {
      const lt = window.MOCK_API.getLiveTrace ? window.MOCK_API.getLiveTrace() : null;
      liveRef.current = lt;
      setLiveTrace(lt ? { scenario: lt.scenario, step: lt.step, tools: lt.tools || [] } : null);
    }, 250);
    return () => clearInterval(t);
  }, []);

  // When live trace fires, lock scenario + step
  useEffect(() => {
    if (!liveTrace) return;
    const idx = AF_SCENARIOS.findIndex(s => s.id === liveTrace.scenario);
    if (idx >= 0) { setScIdx(idx); setStIdx(liveTrace.step); }
  }, [liveTrace?.scenario, liveTrace?.step]);

  // Auto-advance steps → scenarios (skips when live trace is active)
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => {
      if (liveRef.current) return;
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

  // Sync to tweaks-panel activeTrace (lower priority than live trace)
  useEffect(() => {
    if (!activeTrace || activeTrace === 'none' || liveRef.current) return;
    const sid = _ACCENT_TO_SC[activeTrace] || activeTrace;
    const idx = AF_SCENARIOS.findIndex(s => s.id === sid);
    if (idx >= 0) { setScIdx(idx); setStIdx(0); }
  }, [activeTrace]);

  const animated = running || !!liveTrace;

  function selectScenario(i) { setScIdx(i); setStIdx(0); }

  const scenario   = AF_SCENARIOS[scIdx];
  const step       = scenario.steps[stIdx] || scenario.steps[0];
  const edgeDef    = AF_EDGES.find(e => e.id === step.edge);
  const activeNodes = new Set(step.active || []);
  const activeTools = new Set([
    ...(step.tools || []),
    ...((liveTrace && liveTrace.tools) || []),
  ]);
  const isRev      = step.dir === 'rev';

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
        {liveTrace
          ? <span className="af-live-badge">● LIVE</span>
          : running && <span className="af-idle-badge">idle · demo</span>
        }
        <button className="btn ghost af-play-btn"
          onClick={() => { if (!liveTrace) setRunning(r => !r); }}
          disabled={!!liveTrace}
          title={liveTrace ? 'Live request in flight' : (running ? 'Pause auto-loop' : 'Resume auto-loop')}>
          {running || liveTrace
            ? <svg width="12" height="12" viewBox="0 0 12 12"><rect x="1" y="1" width="4" height="10" rx="1" fill="currentColor"/><rect x="7" y="1" width="4" height="10" rx="1" fill="currentColor"/></svg>
            : <svg width="12" height="12" viewBox="0 0 12 12"><polygon points="1,0 12,6 1,12" fill="currentColor"/></svg>
          }
          {running || liveTrace ? 'Pause' : 'Play'}
        </button>
      </div>

      {/* SVG Graph */}
      <div className="af-stage">
        <svg viewBox="0 0 800 480" className="af-svg" preserveAspectRatio="xMidYMid meet">
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
          <rect width="800" height="480" fill="url(#af-grid)" opacity="0.35"/>

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

              {animated && (
                <g>
                  {/* Trailing ring */}
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
                    {animated && (
                      <animate attributeName="opacity" dur="1.2s" repeatCount="indefinite"
                        values="0.9;0.3;0.9"/>
                    )}
                  </circle>
                )}
              </g>
            );
          })}

          {/* Tool connectors — thin static lines from agent → tool */}
          {Object.entries(AF_TOOLS).map(([id, t]) => {
            const parent = AF_NODES[t.parent];
            if (!parent) return null;
            const toolActive = activeTools.has(id);
            return (
              <line key={`tc-${id}`}
                x1={parent.cx} y1={parent.cy + 26}
                x2={t.cx} y2={t.cy}
                stroke={toolActive ? parent.c : 'oklch(0.275 0.010 60)'}
                strokeWidth={toolActive ? 1.4 : 0.9}
                strokeDasharray={toolActive ? '0' : '3 3'}
                opacity={toolActive ? 0.85 : 0.5}/>
            );
          })}

          {/* Tool nodes */}
          {Object.entries(AF_TOOLS).map(([id, t]) => {
            const parent = AF_NODES[t.parent];
            if (!parent) return null;
            const isToolActive = activeTools.has(id);
            const tColor = isToolActive ? parent.c : 'oklch(0.50 0.010 60)';
            const halfW = AF_TW / 2, halfH = AF_TH / 2;
            return (
              <g key={`tn-${id}`} className="af-tool-g">
                {isToolActive && (
                  <rect
                    x={t.cx - halfW - 4} y={t.cy - halfH - 4}
                    width={AF_TW + 8} height={AF_TH + 8} rx="8"
                    fill={parent.c} opacity="0.16"
                    style={{ filter: 'blur(5px)' }}/>
                )}
                <rect
                  x={t.cx - halfW} y={t.cy - halfH}
                  width={AF_TW} height={AF_TH} rx="5"
                  fill={isToolActive ? 'oklch(0.235 0.010 60)' : 'oklch(0.200 0.009 60)'}
                  stroke={tColor}
                  strokeWidth={isToolActive ? 1.2 : 0.8}
                  opacity={isToolActive ? 1 : 0.85}/>
                <text x={t.cx} y={t.cy + 3.5}
                  textAnchor="middle"
                  fill={isToolActive ? 'oklch(0.95 0.004 60)' : 'oklch(0.66 0.008 60)'}
                  fontSize="9.5" fontWeight={isToolActive ? '600' : '500'}
                  fontFamily="Geist Mono, JetBrains Mono, monospace"
                  letterSpacing="-0.2">
                  <tspan opacity="0.85">{t.icon}</tspan>
                  <tspan dx="4">{t.label}</tspan>
                </text>
                {isToolActive && animated && (
                  <circle cx={t.cx + halfW - 6} cy={t.cy - halfH + 5}
                    r="2.2" fill={parent.c} opacity="0.95">
                    <animate attributeName="opacity" dur="0.9s" repeatCount="indefinite"
                      values="0.95;0.25;0.95"/>
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


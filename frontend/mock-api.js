// StandIn — API client.
// Fetches from real backend agents via the serve.py proxy (/api/*).
// Falls back to hardcoded mock data when agents are offline (demo mode).

window.MOCK_API = (() => {
  const TEAMS = ['Engineering', 'Design', 'GTM', 'Product'];

  // ── Hardcoded fallback data (used when agents are offline) ──────────────

  const FALLBACK_USERS = [
    { id: 'alice.chen',     name: 'Alice Chen',     role: 'Product Manager',     team: 'Product',     email: 'alice.chen@novaloop.io' },
    { id: 'derek.vasquez',  name: 'Derek Vasquez',  role: 'Lead Engineer',       team: 'Engineering', email: 'derek.vasquez@novaloop.io' },
    { id: 'priya.mehta',    name: 'Priya Mehta',    role: 'Design Lead',         team: 'Design',      email: 'priya.mehta@novaloop.io' },
    { id: 'sam.okafor',     name: 'Sam Okafor',     role: 'GTM Manager',         team: 'GTM',         email: 'sam.okafor@novaloop.io' },
    { id: 'kai.torres',     name: 'Kai Torres',     role: 'QA Engineer',         team: 'Engineering', email: 'kai.torres@novaloop.io' },
    { id: 'mira.lopez',     name: 'Mira Lopez',     role: 'Frontend Engineer',   team: 'Engineering', email: 'mira.lopez@novaloop.io' },
    { id: 'jules.park',     name: 'Jules Park',     role: 'Backend Engineer',    team: 'Engineering', email: 'jules.park@novaloop.io' },
    { id: 'noor.saleh',     name: 'Noor Saleh',     role: 'Product Designer',    team: 'Design',      email: 'noor.saleh@novaloop.io' },
    { id: 'tariq.bell',     name: 'Tariq Bell',     role: 'Growth Lead',         team: 'GTM',         email: 'tariq.bell@novaloop.io' },
    { id: 'rena.wu',        name: 'Rena Wu',        role: 'Product Analyst',     team: 'Product',     email: 'rena.wu@novaloop.io' },
  ];

  const FALLBACK_EDGES = [
    { from_user:'alice.chen', to_user:'derek.vasquez', type:'meeting',     source_id:'launch_sync_001', label:'Launch Alpha — Go/No-Go Sync', timestamp:'2026-04-28T09:00:00Z', weight:3 },
    { from_user:'alice.chen', to_user:'priya.mehta',   type:'meeting',     source_id:'launch_sync_001', label:'Launch Alpha — Go/No-Go Sync', timestamp:'2026-04-28T09:00:00Z', weight:2 },
    { from_user:'alice.chen', to_user:'sam.okafor',    type:'meeting',     source_id:'launch_sync_001', label:'Launch Alpha — Go/No-Go Sync', timestamp:'2026-04-28T09:00:00Z', weight:2 },
    { from_user:'derek.vasquez', to_user:'priya.mehta',type:'meeting',     source_id:'launch_sync_001', label:'Launch Alpha — Go/No-Go Sync', timestamp:'2026-04-28T09:00:00Z', weight:1 },
    { from_user:'derek.vasquez', to_user:'sam.okafor', type:'meeting',     source_id:'launch_sync_001', label:'Launch Alpha — Go/No-Go Sync', timestamp:'2026-04-28T09:00:00Z', weight:1 },
    { from_user:'priya.mehta',   to_user:'sam.okafor', type:'meeting',     source_id:'launch_sync_001', label:'Launch Alpha — Go/No-Go Sync', timestamp:'2026-04-28T09:00:00Z', weight:1 },
    { from_user:'priya.mehta', to_user:'alice.chen',  type:'meeting',      source_id:'design_review_002', label:'Launch Page Final Design Review', timestamp:'2026-04-24T15:00:00Z', weight:1 },
    { from_user:'priya.mehta', to_user:'sam.okafor',  type:'meeting',      source_id:'design_review_002', label:'Launch Page Final Design Review', timestamp:'2026-04-24T15:00:00Z', weight:1 },
    { from_user:'priya.mehta', to_user:'noor.saleh',  type:'meeting',      source_id:'design_review_002', label:'Launch Page Final Design Review', timestamp:'2026-04-24T15:00:00Z', weight:2 },
    { from_user:'derek.vasquez', to_user:'kai.torres',type:'meeting',      source_id:'eng_standup_003', label:'Engineering Daily Standup', timestamp:'2026-04-25T09:30:00Z', weight:4 },
    { from_user:'derek.vasquez', to_user:'mira.lopez',type:'meeting',      source_id:'eng_standup_003', label:'Engineering Daily Standup', timestamp:'2026-04-25T09:30:00Z', weight:4 },
    { from_user:'derek.vasquez', to_user:'jules.park',type:'meeting',      source_id:'eng_standup_003', label:'Engineering Daily Standup', timestamp:'2026-04-25T09:30:00Z', weight:4 },
    { from_user:'kai.torres',    to_user:'mira.lopez',type:'meeting',      source_id:'eng_standup_003', label:'Engineering Daily Standup', timestamp:'2026-04-25T09:30:00Z', weight:2 },
    { from_user:'priya.mehta',   to_user:'alice.chen', type:'slack_thread', source_id:'msg_design_launch_ready', label:'#launch-alpha · Launch page ready to ship', timestamp:'2026-04-25T08:47:00Z', weight:2 },
    { from_user:'derek.vasquez', to_user:'kai.torres', type:'slack_thread', source_id:'msg_eng_api_change',      label:'#engineering · /v1→/v2 checkout migration', timestamp:'2026-04-25T02:18:00Z', weight:3 },
    { from_user:'derek.vasquez', to_user:'alice.chen', type:'slack_thread', source_id:'msg_alice_status_check',  label:'#launch-alpha · NOVA-142 status thread',    timestamp:'2026-04-25T09:00:00Z', weight:2 },
    { from_user:'sam.okafor',    to_user:'tariq.bell', type:'slack_thread', source_id:'msg_gtm_email_preview',   label:'#launch-alpha · Launch email pricing review', timestamp:'2026-04-25T09:10:00Z', weight:2 },
    { from_user:'kai.torres',    to_user:'mira.lopez', type:'slack_thread', source_id:'msg_qa_sign_off_hold',    label:'#qa · Smoke test failing /v2/checkout',      timestamp:'2026-04-25T08:00:00Z', weight:1 },
    { from_user:'rena.wu',       to_user:'alice.chen', type:'slack_thread', source_id:'msg_metrics_dash',        label:'#product · Activation metrics +12%',         timestamp:'2026-04-24T18:30:00Z', weight:1 },
    { from_user:'derek.vasquez', to_user:'kai.torres', type:'jira', source_id:'NOVA-142', label:'NOVA-142 — Update launch page for v2 checkout', timestamp:'2026-04-25T02:30:00Z', weight:2 },
    { from_user:'derek.vasquez', to_user:'alice.chen', type:'jira', source_id:'NOVA-139', label:'NOVA-139 — Gemini summarization (done)', timestamp:'2026-04-20T10:00:00Z', weight:1 },
    { from_user:'priya.mehta',   to_user:'alice.chen', type:'jira', source_id:'NOVA-140', label:'NOVA-140 — Design QA handoff (done)',     timestamp:'2026-04-22T09:00:00Z', weight:1 },
    { from_user:'sam.okafor',    to_user:'alice.chen', type:'jira', source_id:'NOVA-141', label:'NOVA-141 — GTM launch email review',     timestamp:'2026-04-23T11:00:00Z', weight:1 },
    { from_user:'kai.torres',    to_user:'derek.vasquez', type:'jira', source_id:'NOVA-143', label:'NOVA-143 — QA smoke sign-off (blocked)', timestamp:'2026-04-25T08:05:00Z', weight:2 },
    { from_user:'mira.lopez',    to_user:'derek.vasquez', type:'jira', source_id:'NOVA-144', label:'NOVA-144 — Frontend retry/backoff',     timestamp:'2026-04-24T11:20:00Z', weight:1 },
    { from_user:'jules.park',    to_user:'derek.vasquez', type:'jira', source_id:'NOVA-145', label:'NOVA-145 — Migrate /v2 in payment service', timestamp:'2026-04-25T03:10:00Z', weight:1 },
    { from_user:'noor.saleh',    to_user:'priya.mehta', type:'jira', source_id:'NOVA-138', label:'NOVA-138 — Empty state illustrations',   timestamp:'2026-04-21T14:00:00Z', weight:1 },
  ];

  const FALLBACK_APPROVALS = [
    {
      action_id: 'a-9f02-blocker-nova142', action_type: 'send_slack',
      title: 'NOVA-142 — Update launch page for v2 checkout',
      summary: 'Engineering is blocked on the v1→v2 checkout API migration. The launch page still calls /v1/checkout and QA cannot sign off until it merges.',
      team: 'Engineering', owner: 'derek.vasquez', ownerName: 'Derek Vasquez',
      status: 'blocked', risk: 'high', created_at: '2026-04-25T09:05:00Z', stub: true,
      payload: { channel: '#engineering', text: 'Heads up: NOVA-142 still blocking launch. Need a merge of the /v2 fix before QA can re-run smoke.' },
      escalation: { required: true, reason: 'Design reports launch page ready. Engineering reports checkout integration blocked (NOVA-142). These claims directly conflict.', recommended: 'Schedule 15-minute escalation with Design and Engineering only.' },
    },
    {
      action_id: 'a-3a11-design-ready', action_type: 'send_slack',
      title: 'Launch page asset package — final',
      summary: 'Priya marked the launch page as ready and handed off assets. Awaiting confirmation from Engineering integration.',
      team: 'Design', owner: 'priya.mehta', ownerName: 'Priya Mehta',
      status: 'ready', risk: 'medium', created_at: '2026-04-25T08:47:00Z', stub: true,
      payload: { channel: '#launch-alpha', text: 'Final launch page assets are signed off — handing to Engineering for integration verification.' },
    },
    {
      action_id: 'a-7c44-gtm-email', action_type: 'send_email',
      title: 'NOVA-141 — Launch email legal review',
      summary: 'GTM email is drafted; pricing line awaiting legal sign-off before scheduling the send.',
      team: 'GTM', owner: 'sam.okafor', ownerName: 'Sam Okafor',
      status: 'in_review', risk: 'medium', created_at: '2026-04-25T08:45:00Z', stub: true,
      payload: { to: 'launch-list@novaloop.io', subject: 'Introducing Checkout AI Assistant — Live Monday', body: 'Pricing TBD by legal …' },
    },
    {
      action_id: 'a-4d20-qa-blocker', action_type: 'create_jira',
      title: 'NOVA-143 — QA smoke sign-off blocked',
      summary: 'QA cannot complete the smoke test until NOVA-142 merges. Status held at blocked.',
      team: 'Engineering', owner: 'kai.torres', ownerName: 'Kai Torres',
      status: 'blocked', risk: 'high', created_at: '2026-04-25T08:05:00Z', stub: false,
      payload: { project: 'NOVA', issuetype: 'Task', summary: 'Re-run smoke once NOVA-142 merges' },
    },
    {
      action_id: 'a-8e51-product-brief', action_type: 'schedule_meeting',
      title: 'Cross-team Go/No-Go reschedule',
      summary: 'Product is requesting a 15-minute escalation between Design and Engineering ahead of Monday.',
      team: 'Product', owner: 'alice.chen', ownerName: 'Alice Chen',
      status: 'in_review', risk: 'high', created_at: '2026-04-25T09:12:00Z', stub: true,
      payload: { attendees: ['priya.mehta', 'derek.vasquez', 'alice.chen'], when: '2026-04-25T16:00:00Z', title: '15-min escalation — Launch page integration' },
    },
  ];

  // ── Mutable in-memory state ─────────────────────────────────────────────

  let _approvals = FALLBACK_APPROVALS.slice();
  let _users     = FALLBACK_USERS.slice();
  let _edges     = FALLBACK_EDGES.slice();
  let _source    = 'demo';
  let _liveTrace = null; // { scenario: 'status'|'history'|'action', step: 0-3 } | null

  // Feed starts empty — entries appear as real requests fire.
  // Backend action_log is merged in via _refreshFeed().
  let _feed = [];

  let _healthState = {
    status:     { online: true,  Gemini: true,  MongoDB: true  },
    perform:    { online: true,  Gemini: true,  MongoDB: true  },
    historical: { online: true,  Gemini: true,  MongoDB: false },
  };

  const HEALTH_AGENTS = [
    { id: 'status',     name: 'Status Agent',   port: 8007, configured: { Gemini: true, MongoDB: true  } },
    { id: 'perform',    name: 'Perform Action', port: 8008, configured: { Gemini: true, MongoDB: true  } },
    { id: 'historical', name: 'Historical',     port: 8009, configured: { Gemini: true, MongoDB: false } },
  ];

  // ── Backend fetch helpers ───────────────────────────────────────────────

  const BASE = {
    perform: '/api/perform',
    status:  '/api/status',
    history: '/api/history',
  };

  async function _get(url) {
    const r = await fetch(url, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  }

  async function _post(url, body) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(6000),
    });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  }

  // Long-timeout POST for operations that run the full agent pipeline (~30s)
  async function _postLong(url, body) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(45000),
    });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  }

  // Map BE PendingAction → FE card shape
  function _beToCard(a) {
    let payload = {};
    try { payload = JSON.parse(a.payload_json || '{}'); } catch (_) {}
    let escalation = null;
    try {
      const e = JSON.parse(a.escalation_json || 'null');
      if (e && e.required) escalation = e;
    } catch (_) {}
    return {
      action_id:   a.action_id,
      action_type: a.action_type,
      title:       a.title       || a.action_type.replace(/_/g, ' '),
      summary:     a.summary     || '',
      team:        a.team        || '',
      owner:       a.owner       || '',
      ownerName:   a.owner_name  || '',
      status:      a.ticket_status || 'in_review',
      risk:        a.risk        || 'medium',
      created_at:  a.created_at  || '',
      stub:        a.stub        ?? true,
      payload,
      escalation,
    };
  }

  // ── Refresh loops ───────────────────────────────────────────────────────

  async function _refreshApprovals() {
    try {
      const data = await _get(`${BASE.perform}/approvals`);
      if (Array.isArray(data.actions) && data.actions.length > 0) {
        _approvals = data.actions.map(_beToCard);
        _source = 'mongodb';
      }
    } catch (_) { /* keep fallback */ }
  }

  async function _refreshGraph() {
    try {
      const data = await _get(`${BASE.perform}/graph`);
      if (data.nodes && data.edges) {
        _users = data.nodes;
        _edges = data.edges;
        if (data.source && data.source !== 'demo') _source = data.source;
      }
    } catch (_) {}
  }

  async function _refreshFeed() {
    try {
      const data = await _get(`${BASE.perform}/log`);
      if (Array.isArray(data.entries) && data.entries.length > 0) {
        const seenKeys = new Set(_feed.map(e => `${e.ts}|${e.agent}|${e.tool}`));
        const newEntries = data.entries
          .map(e => ({ ts: e.ts, agent: e.agent, tool: e.tool, status: e.status, stub: e.stub ?? false, meta: e.meta || '' }))
          .filter(e => !seenKeys.has(`${e.ts}|${e.agent}|${e.tool}`));
        if (newEntries.length > 0) {
          _feed = [..._feed, ...newEntries].sort((a, b) => b.ts.localeCompare(a.ts)).slice(0, 80);
        }
      }
    } catch (_) { /* keep local feed */ }
  }

  async function _refreshHealth() {
    const checks = [
      { id: 'status',     url: `${BASE.status}/health`  },
      { id: 'perform',    url: `${BASE.perform}/health` },
      { id: 'historical', url: `${BASE.history}/health` },
    ];
    for (const { id, url } of checks) {
      try {
        const h = await _get(url);
        // Each agent has slightly different health fields — map explicitly
        const geminiOk  = id === 'perform'
          ? true  // perform_action doesn't use Gemini directly
          : h.gemini === 'configured';
        const mongoOk   = id === 'historical'
          ? h.tier1 === 'ready'        // historical uses tier1 (Atlas vector)
          : (h.mongodb === 'configured' || h.mongodb === 'connected');
        _healthState[id] = { online: h.status === 'ok', Gemini: geminiOk, MongoDB: mongoOk };
      } catch (_) {
        _healthState[id] = { ..._healthState[id], online: false };
      }
    }
  }

  // Initial fetch + polling
  Promise.all([_refreshApprovals(), _refreshGraph(), _refreshHealth(), _refreshFeed()]);
  setInterval(_refreshApprovals, 5000);
  setInterval(_refreshGraph,     30000);
  setInterval(_refreshHealth,    8000);
  setInterval(_refreshFeed,      10000);

  // ── Local feed helper ───────────────────────────────────────────────────

  function _pushFeed(agent, tool, status, stub, meta) {
    _feed.unshift({ ts: new Date().toISOString(), agent, tool, status, stub, meta: meta || '', _new: true });
    _feed = _feed.slice(0, 80);
  }

  // ── Public API ──────────────────────────────────────────────────────────

  return {
    TEAMS,

    listUsers:     () => _users.slice(),
    listEdges:     () => _edges.slice(),
    listApprovals: () => _approvals.slice(),
    listFeed:      () => _feed.slice(),
    pushFeed:      _pushFeed,

    healthAgents: () => HEALTH_AGENTS,
    healthState:  () => _healthState,

    setHealth: (id, patch) => { _healthState[id] = { ..._healthState[id], ...patch }; },
    getSource: () => _source,
    setSource: (s) => { _source = s; },
    getTrace:  () => null,
    setTrace:  () => {},

    approve: async (id) => {
      _approvals = _approvals.filter(a => a.action_id !== id);
      _pushFeed('perform_action', 'approve', 'DONE', false, id.slice(0, 12));
      _liveTrace = { scenario: 'action', step: 1 };
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = { scenario: 'action', step: 2 }; }, 350);
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = { scenario: 'action', step: 3 }; }, 700);
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = null; }, 1300);
      try { await _post(`${BASE.perform}/approvals/approve`, { action_id: id, approver: 'dashboard' }); } catch (_) {}
    },

    reject: async (id) => {
      _approvals = _approvals.filter(a => a.action_id !== id);
      _pushFeed('perform_action', 'reject', 'DONE', false, id.slice(0, 12));
      _liveTrace = { scenario: 'action', step: 1 };
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = { scenario: 'action', step: 2 }; }, 350);
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = { scenario: 'action', step: 3 }; }, 700);
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = null; }, 1300);
      try { await _post(`${BASE.perform}/approvals/reject`, { action_id: id, reason: 'rejected via dashboard' }); } catch (_) {}
    },

    edgesFor: (userId) => _edges
      .filter(e => e.from_user === userId || e.to_user === userId)
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp)),

    getLiveTrace: () => _liveTrace,

    // ── Brief & RAG HTTP endpoints ────────────────────────────────────────

    fetchBrief: async (topic, userEmail = 'demo@standin.ai') => {
      _liveTrace = { scenario: 'status', step: 0 };
      const t1 = setTimeout(() => { if (_liveTrace?.scenario === 'status') _liveTrace = { scenario: 'status', step: 1 }; }, 900);
      const t2 = setTimeout(() => { if (_liveTrace?.scenario === 'status') _liveTrace = { scenario: 'status', step: 2 }; }, 2400);
      try {
        const result = await _postLong(`${BASE.status}/brief`, { topic, user_email: userEmail });
        clearTimeout(t1); clearTimeout(t2);
        _liveTrace = { scenario: 'status', step: 3 };
        _pushFeed('orchestrator', 'classify → status', 'DONE', false, (topic || '').slice(0, 28));
        if (result && result.mode !== 'error') {
          const live = result.mode === 'live';
          _pushFeed('status_agent', 'gather',     'DONE', !live, `${result.role_statuses?.length || 0} roles`);
          _pushFeed('status_agent', 'synthesise', 'DONE', !live, `mode=${result.mode}`);
          _pushFeed('status_agent', 'rule_engine','DONE', false,  result.escalation_required ? 'escalation=true' : 'clean');
          if ((result.evidence_passports?.length || 0) > 0) {
            _pushFeed('status_agent', 'passports', 'DONE', false, `n=${result.evidence_passports.length}`);
          }
          _source = result.mode || 'live';
        }
        setTimeout(() => { if (_liveTrace?.scenario === 'status') _liveTrace = null; }, 1600);
        return result;
      } catch (e) {
        clearTimeout(t1); clearTimeout(t2);
        _liveTrace = null;
        console.warn('fetchBrief failed:', e);
        return null;
      }
    },

    askHistory: async (question) => {
      // Steps 0-5 match the 6-step fan-out scenario in AF_SCENARIOS['history']
      _liveTrace = { scenario: 'history', step: 0 };
      // step 1: orch → historical (fan-out arm 1)
      const t1 = setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = { scenario: 'history', step: 1 }; }, 600);
      // step 2: orch → status (fan-out arm 2, parallel)
      const t2 = setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = { scenario: 'history', step: 2 }; }, 1100);
      try {
        const result = await _postLong(`${BASE.history}/ask`, { question });
        clearTimeout(t1); clearTimeout(t2);
        // step 3: historical → orch (RAGResponse arrives)
        _liveTrace = { scenario: 'history', step: 3 };
        _pushFeed('orchestrator', 'classify → fan-out', 'DONE', false, (question || '').slice(0, 28));
        if (result) {
          const method = result.retrieval_method || 'unknown';
          const tier1  = method === 'vector_search';
          const tier2  = method === 'keyword_search' || method === 'keyword';
          _pushFeed('historical', 'tier1_vector',  tier1 ? 'DONE' : 'MISS', !tier1, tier1 ? `conf=${result.confidence?.toFixed(2)}` : 'no match');
          if (!tier1) {
            _pushFeed('historical', 'tier2_keyword', tier2 ? 'DONE' : 'MISS', false, tier2 ? 'bm25 hit' : 'no match');
          }
          _pushFeed('historical', 'synthesise', 'DONE', false, `conf=${result.confidence?.toFixed(2) || '?'}`);
        }
        // step 4: status → orch (FullBriefResponse arrives, merge triggers)
        setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = { scenario: 'history', step: 4 }; }, 400);
        _pushFeed('status_agent', 'gather+synthesise', 'DONE', false, 'fan-out arm 2');
        // step 5: orch → user (merged reply)
        setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = { scenario: 'history', step: 5 }; }, 900);
        _pushFeed('orchestrator', 'merge + reply', 'DONE', false, 'historical + live status');
        setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = null; }, 1600);
        return result;
      } catch (e) {
        clearTimeout(t1); clearTimeout(t2);
        _liveTrace = null;
        console.warn('askHistory failed:', e);
        return null;
      }
    },
  };
})();

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

  // ── Notifications (live, cursor-polled) ────────────────────────────────
  let _notifications  = [];   // newest first
  let _notifCursor    = null; // ISO ts of most recent seen notification
  let _notifUnread    = 0;
  let _notifListeners = [];   // (notifs, unread, justArrived) => void
  let _firstNotifPoll = true;

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

  async function _post(url, body, timeoutMs = 6000) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  }

  // Long-timeout POST for operations that run the full agent pipeline (~30s)
  async function _postLong(url, body) {
    return _post(url, body, 45000);
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
      if (Array.isArray(data.actions)) {
        const live = data.actions.map(_beToCard);
        const liveIds = new Set(live.map(c => c.action_id));
        // Merge: live (real backend) cards first, then any optimistic cards not
        // yet in backend, then any seeded fallback cards. Keeps the demo full.
        const optimistic = _approvals.filter(a =>
          a.action_id.startsWith('pending-') && !liveIds.has(a.action_id)
        );
        const fallbacks = FALLBACK_APPROVALS.filter(a => !liveIds.has(a.action_id));
        _approvals = [...live, ...optimistic, ...fallbacks];
        if (live.length > 0) _source = 'mongodb';
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

  // Map a (agent, tool) pair from backend feed → tool-node id used by agent-flow graph
  function _toolKey(agent, tool) {
    const a = (agent || '').toLowerCase();
    const t = (tool || '').toLowerCase();
    if (a.startsWith('status')) {
      if (t.includes('gather'))      return 'status.gather';
      if (t.includes('rag'))         return 'status.rag';
      if (t.includes('synth'))       return 'status.synth';
      if (t.includes('contradict') || t.includes('rule')) return 'status.contradict';
      if (t.includes('passport'))    return 'status.passports';
    }
    if (a.startsWith('hist')) {
      if (t.includes('vector') || t.includes('tier1')) return 'hist.vector';
      if (t.includes('keyword')|| t.includes('tier2')) return 'hist.keyword';
      if (t.includes('synth'))                          return 'hist.synth';
      if (t.includes('mongo'))                          return 'hist.mongo';
    }
    if (a.startsWith('perform')) {
      if (t.includes('approv'))    return 'perf.approval';
      if (t.includes('slack'))     return 'perf.slack';
      if (t.includes('jira'))      return 'perf.jira';
      if (t.includes('calendar') || t.includes('meeting')) return 'perf.calendar';
      if (t.includes('email') || t.includes('gmail'))      return 'perf.gmail';
    }
    return null;
  }

  // Briefly flash a tool node when a fresh backend feed entry arrives
  function _flashTool(toolId, scenario) {
    if (!toolId) return;
    const sc = scenario || (toolId.startsWith('hist.') ? 'history'
                          : toolId.startsWith('perf.') ? 'action'
                          : 'status');
    const prev = _liveTrace || { scenario: sc, step: 0, tools: [] };
    const tools = Array.from(new Set([...(prev.tools || []), toolId]));
    _liveTrace = { ...prev, scenario: sc, tools };
    setTimeout(() => {
      if (!_liveTrace) return;
      _liveTrace = { ..._liveTrace, tools: (_liveTrace.tools || []).filter(x => x !== toolId) };
    }, 1400);
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
          // Flash matching tool nodes for any genuinely new backend tool calls.
          newEntries.forEach(e => _flashTool(_toolKey(e.agent, e.tool)));
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

  async function _refreshNotifications() {
    try {
      const body = { limit: 30, include_read: true };
      if (_notifCursor) body.since = _notifCursor;
      const data = await _post(`${BASE.perform}/notifications/list`, body);
      const items = Array.isArray(data?.notifications) ? data.notifications : [];
      const arrivals = [];
      if (items.length > 0) {
        // Backend returns newest-first; merge avoiding dupes by id.
        const known = new Set(_notifications.map(n => n.id));
        for (const n of items) {
          if (!known.has(n.id)) {
            _notifications.unshift(n);
            arrivals.push(n);
          }
        }
        _notifications = _notifications.slice(0, 80);
        if (data.cursor) _notifCursor = data.cursor;
        else _notifCursor = items[0].ts;
      }
      if (typeof data?.unread_count === 'number') _notifUnread = data.unread_count;
      const justArrived = _firstNotifPoll ? [] : arrivals;
      _firstNotifPoll = false;
      _notifListeners.forEach(fn => { try { fn(_notifications.slice(), _notifUnread, justArrived); } catch (_) {} });
    } catch (_) { /* keep state */ }
  }

  // Initial fetch + polling
  Promise.all([_refreshApprovals(), _refreshGraph(), _refreshHealth(), _refreshFeed(), _refreshNotifications()]);
  setInterval(_refreshApprovals,     5000);
  setInterval(_refreshGraph,         30000);
  setInterval(_refreshHealth,        8000);
  setInterval(_refreshFeed,          10000);
  setInterval(_refreshNotifications, 2500);

  // ── Local feed helper ───────────────────────────────────────────────────

  function _pushFeed(agent, tool, status, stub, meta) {
    _feed.unshift({ ts: new Date().toISOString(), agent, tool, status, stub, meta: meta || '', _new: true });
    _feed = _feed.slice(0, 80);
    _flashTool(_toolKey(agent, tool));
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
      const action = _approvals.find(a => a.action_id === id);
      const toolMap = {
        send_slack: 'perf.slack', draft_slack: 'perf.slack',
        send_email: 'perf.gmail',
        schedule_meeting: 'perf.calendar',
        create_jira: 'perf.jira', update_jira_status: 'perf.jira',
      };
      const execTool = toolMap[action?.action_type] || 'perf.slack';
      _approvals = _approvals.filter(a => a.action_id !== id);
      _pushFeed('perform_action', 'approve', 'DONE', false, id.slice(0, 12));
      _liveTrace = { scenario: 'action', step: 1, tools: [] };
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = { scenario: 'action', step: 2, tools: ['perf.approval'] }; }, 350);
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = { scenario: 'action', step: 3, tools: [execTool] }; }, 800);
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = { scenario: 'action', step: 4, tools: [] }; }, 1500);
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = null; }, 2200);
      try { await _post(`${BASE.perform}/approvals/approve`, { action_id: id, approver: 'dashboard' }); } catch (_) {}
    },

    reject: async (id) => {
      _approvals = _approvals.filter(a => a.action_id !== id);
      _pushFeed('perform_action', 'reject', 'DONE', false, id.slice(0, 12));
      _liveTrace = { scenario: 'action', step: 1, tools: [] };
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = { scenario: 'action', step: 2, tools: ['perf.approval'] }; }, 350);
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = null; }, 1300);
      try { await _post(`${BASE.perform}/approvals/reject`, { action_id: id, reason: 'rejected via dashboard' }); } catch (_) {}
    },

    edgesFor: (userId) => _edges
      .filter(e => e.from_user === userId || e.to_user === userId)
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp)),

    // Submit a fresh action (e.g. "Schedule sync" on the escalation card).
    // Optimistically inserts a pending_approval card so the UI updates instantly,
    // then POSTs to the backend; on failure the optimistic card stays so the
    // demo always has visible feedback.
    submitAction: async ({ action_type, payload, title, summary, team, owner, owner_name, risk = 'high', priority = 'urgent', ticket_status = 'in_review' }) => {
      const tempId = `pending-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const card = {
        action_id: tempId, action_type,
        title: title || action_type.replace(/_/g, ' '),
        summary: summary || '',
        team: team || '', owner: owner || '', ownerName: owner_name || '',
        status: ticket_status, risk,
        created_at: new Date().toISOString(),
        stub: true,
        payload,
      };
      _approvals = [card, ..._approvals];
      _pushFeed('orchestrator', `submit:${action_type}`, 'DONE', false, (title || '').slice(0, 36));
      _pushFeed('perform_action', 'approval_gate', 'PENDING', false, 'awaiting human');
      // Light up the perform-agent path on the graph
      _liveTrace = { scenario: 'action', step: 1, tools: [] };
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = { scenario: 'action', step: 2, tools: ['perf.approval'] }; }, 350);
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = null; }, 2200);
      try {
        const resp = await _post(`${BASE.perform}/actions`, {
          action_type,
          payload: typeof payload === 'string' ? payload : JSON.stringify(payload || {}),
          title: card.title, summary: card.summary, team, owner, owner_name,
          ticket_status, risk, priority,
        });
        if (resp && resp.action_id && resp.action_id !== tempId) {
          // Replace optimistic id with real one so approve/reject hits backend correctly.
          _approvals = _approvals.map(a => a.action_id === tempId ? { ...a, action_id: resp.action_id } : a);
        }
        return resp;
      } catch (e) {
        console.warn('submitAction failed, keeping optimistic card:', e);
        return { action_id: tempId, action_type, success: false, pending_approval: true, error: String(e) };
      }
    },

    scheduleEscalationSync: async (escalation) => {
      const reason = (escalation && escalation.escalation && escalation.escalation.reason) || '';
      const teamsInReason = ['Engineering', 'Design', 'GTM', 'Product'].filter(t => reason.includes(t));
      // Calendar API needs real emails — match the seeded NovaLoop users
      const teamMap = {
        Engineering: { id: 'derek.vasquez', name: 'Derek Vasquez', email: 'derek.vasquez@novaloop.io' },
        Design:      { id: 'priya.mehta',   name: 'Priya Mehta',   email: 'priya.mehta@novaloop.io' },
        GTM:         { id: 'sam.okafor',    name: 'Sam Okafor',    email: 'sam.okafor@novaloop.io' },
        Product:     { id: 'alice.chen',    name: 'Alice Chen',    email: 'alice.chen@novaloop.io' },
      };
      const attendees = (teamsInReason.length ? teamsInReason : ['Engineering', 'Design'])
        .map(t => teamMap[t]).filter(Boolean);
      const durationMin = 15;
      const start = new Date(Date.now() + 60 * 60 * 1000);
      const end   = new Date(start.getTime() + durationMin * 60 * 1000);
      const startIso = start.toISOString().replace(/\.\d{3}Z$/, 'Z');
      const endIso   = end.toISOString().replace(/\.\d{3}Z$/, 'Z');
      const titleStr = `${teamsInReason.join(' × ') || 'Escalation'} sync`;
      return window.MOCK_API.submitAction({
        action_type: 'schedule_meeting',
        title: `${titleStr} — ${durationMin} min`,
        summary: escalation?.escalation?.recommended || 'Escalation sync',
        team: 'Product', owner: 'alice.chen', owner_name: 'Alice Chen',
        risk: 'high', priority: 'urgent', ticket_status: 'in_review',
        // Match _action_schedule_meeting expected fields (start_time/end_time, email attendees)
        payload: {
          title: titleStr,
          summary: titleStr,
          attendees: attendees.map(a => a.email),
          start_time: startIso,
          end_time: endIso,
          duration_minutes: durationMin,
          time_zone: 'UTC',
          description: `${escalation?.escalation?.reason || ''}\n\nRecommended: ${escalation?.escalation?.recommended || ''}\n\nAgenda:\n- Reconcile conflicting status reports\n- Decide go/no-go for launch`,
        },
      });
    },

    // ── Agent-to-agent resolution conversation ───────────────────────────
    //
    // Kicks off a backend conversation in which orchestrator delegates to
    // status / historical agents and converges on a resolution. Returns the
    // conversation_id so the UI can poll for streamed messages.
    acceptAndStart: async (ticket) => {
      const card = ticket || {};
      _pushFeed('orchestrator', `accept:${card.action_type || 'action'}`, 'DONE', false, (card.title || '').slice(0, 36));
      _liveTrace = { scenario: 'action', step: 1, tools: [] };
      setTimeout(() => { if (_liveTrace?.scenario === 'action') _liveTrace = { scenario: 'action', step: 2, tools: ['perf.approval'] }; }, 350);
      try {
        const resp = await _postLong(`${BASE.perform}/conversations/start`, {
          action_id:   card.action_id || '',
          action_type: card.action_type || '',
          title:       card.title || '',
          owner:       card.owner || '',
          team:        card.team  || '',
          summary:     card.summary || '',
        });
        return resp; // { conversation_id, action_id, status }
      } catch (e) {
        console.warn('acceptAndStart failed:', e);
        return { conversation_id: '', action_id: card.action_id || '', status: 'failed', error: String(e) };
      }
    },

    pollConversation: async (conversationId) => {
      if (!conversationId) return null;
      try {
        return await _post(`${BASE.perform}/conversations/get`, { conversation_id: conversationId }, 15000);
      } catch (e) {
        console.warn('pollConversation failed:', e);
        return null;
      }
    },

    finalizeAccepted: (actionId) => {
      // Remove the card locally once the conversation has resolved.
      _approvals = _approvals.filter(a => a.action_id !== actionId);
      _liveTrace = null;
    },

    getLiveTrace: () => _liveTrace,

    // ── Notifications ────────────────────────────────────────────────────
    listNotifications: () => _notifications.slice(),
    unreadNotifications: () => _notifUnread,
    onNotifications: (fn) => {
      if (typeof fn !== 'function') return () => {};
      _notifListeners.push(fn);
      // Fire once with current snapshot so subscribers render immediately.
      try { fn(_notifications.slice(), _notifUnread, []); } catch (_) {}
      return () => { _notifListeners = _notifListeners.filter(x => x !== fn); };
    },
    markNotificationsRead: async (ids) => {
      const idArr = Array.isArray(ids) ? ids : [ids].filter(Boolean);
      if (idArr.length === 0) return;
      _notifications = _notifications.map(n => idArr.includes(n.id) ? { ...n, read: true } : n);
      _notifUnread = Math.max(0, _notifUnread - idArr.length);
      _notifListeners.forEach(fn => { try { fn(_notifications.slice(), _notifUnread, []); } catch (_) {} });
      try { await _post(`${BASE.perform}/notifications/mark_read`, { ids: idArr, all: false }); } catch (_) {}
    },
    markAllNotificationsRead: async () => {
      _notifications = _notifications.map(n => ({ ...n, read: true }));
      _notifUnread = 0;
      _notifListeners.forEach(fn => { try { fn(_notifications.slice(), _notifUnread, []); } catch (_) {} });
      try { await _post(`${BASE.perform}/notifications/mark_read`, { all: true }); } catch (_) {}
    },

    // ── Brief & RAG HTTP endpoints ────────────────────────────────────────

    fetchBrief: async (topic, userEmail = 'demo@standin.ai') => {
      // Step 0: user → orch
      _liveTrace = { scenario: 'status', step: 0, tools: [] };
      // Step 1: orch → status (FullBriefRequest)
      const t1 = setTimeout(() => { if (_liveTrace?.scenario === 'status') _liveTrace = { scenario: 'status', step: 1, tools: [] }; }, 700);
      // Step 2: gather + rag (tool nodes light up on Status agent)
      const t2 = setTimeout(() => { if (_liveTrace?.scenario === 'status') _liveTrace = { scenario: 'status', step: 2, tools: ['status.gather', 'status.rag'] }; }, 1400);
      // Step 3: synthesise tool fires
      const t3 = setTimeout(() => { if (_liveTrace?.scenario === 'status') _liveTrace = { scenario: 'status', step: 3, tools: ['status.synth'] }; }, 3200);
      // Step 4: contradict + passports
      const t4 = setTimeout(() => { if (_liveTrace?.scenario === 'status') _liveTrace = { scenario: 'status', step: 4, tools: ['status.contradict', 'status.passports'] }; }, 5000);
      try {
        const result = await _postLong(`${BASE.status}/brief`, { topic, user_email: userEmail });
        clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4);
        // Step 5: status → orch (FullBriefResponse)
        _liveTrace = { scenario: 'status', step: 5, tools: [] };
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
        // Step 6: orch → user
        setTimeout(() => { if (_liveTrace?.scenario === 'status') _liveTrace = { scenario: 'status', step: 6, tools: [] }; }, 700);
        setTimeout(() => { if (_liveTrace?.scenario === 'status') _liveTrace = null; }, 2200);
        return result;
      } catch (e) {
        clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4);
        _liveTrace = null;
        console.warn('fetchBrief failed:', e);
        return null;
      }
    },

    askHistory: async (question) => {
      _liveTrace = { scenario: 'history', step: 0, tools: [] };
      // step 1: orch → historical (fan-out arm 1)
      const t1 = setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = { scenario: 'history', step: 1, tools: [] }; }, 500);
      // step 2: vector + mongo tools fire on historical
      const t2 = setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = { scenario: 'history', step: 2, tools: ['hist.vector', 'hist.mongo'] }; }, 1100);
      // step 3: historical synthesise tool
      const t3 = setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = { scenario: 'history', step: 3, tools: ['hist.synth'] }; }, 2400);
      // step 4: status arm fan-out (gather + rag + synth on status agent)
      const t4 = setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = { scenario: 'history', step: 4, tools: ['status.gather', 'status.rag', 'status.synth'] }; }, 3600);
      try {
        const result = await _postLong(`${BASE.history}/ask`, { question });
        clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4);
        _liveTrace = { scenario: 'history', step: 5, tools: [] };
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
        _pushFeed('status_agent', 'gather+synthesise', 'DONE', false, 'fan-out arm 2');
        setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = { scenario: 'history', step: 6, tools: [] }; }, 900);
        _pushFeed('orchestrator', 'merge + reply', 'DONE', false, 'historical + live status');
        setTimeout(() => { if (_liveTrace?.scenario === 'history') _liveTrace = null; }, 2200);
        return result;
      } catch (e) {
        clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4);
        _liveTrace = null;
        console.warn('askHistory failed:', e);
        return null;
      }
    },
  };
})();

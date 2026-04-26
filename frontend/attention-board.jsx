// StandIn — Attention Board view.

const _RISK_RANK   = { high: 0, medium: 1, low: 2 };
const _STATUS_RANK = { blocked: 0, in_review: 1, ready: 2 };

function AttentionBoard({ tweaks }) {
  const [approvals, setApprovals] = useState(() => window.MOCK_API.listApprovals());
  const [resolving, setResolving] = useState({});
  const [chat, setChat] = useState(null); // { ticket, conversationId, state }
  const [filter, setFilter] = useState('all');
  const [teamFilter, setTeamFilter] = useState('all');
  const [riskFilter, setRiskFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [briefLoading, setBriefLoading] = useState(false);
  const [brief, setBrief] = useState(null);
  const [historyResult, setHistoryResult] = useState(null);
  const [queryMode, setQueryMode] = useState('status');
  const queryInputRef = useRef(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    const t = setInterval(() => setApprovals(window.MOCK_API.listApprovals()), 3000);
    return () => clearInterval(t);
  }, []);

  // "/" focuses the query input (unless already in a field)
  useEffect(() => {
    function onKey(e) {
      if (e.key !== '/') return;
      const tag = (document.activeElement?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea') return;
      e.preventDefault();
      queryInputRef.current?.focus();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const escalation = useMemo(() => approvals.find(a => a.escalation && a.escalation.required), [approvals]);

  const stats = useMemo(() => {
    const byStatus = { blocked: 0, in_review: 0, ready: 0 };
    const byRisk = { high: 0, medium: 0, low: 0 };
    const byTeam = {};
    approvals.forEach(a => {
      if (byStatus[a.status] !== undefined) byStatus[a.status]++;
      if (byRisk[a.risk] !== undefined) byRisk[a.risk]++;
      byTeam[a.team] = (byTeam[a.team] || 0) + 1;
    });
    return {
      total: approvals.length,
      blocked: byStatus.blocked,
      in_review: byStatus.in_review,
      ready: byStatus.ready,
      high: byRisk.high,
      byTeam,
    };
  }, [approvals]);

  const filtered = useMemo(() => {
    return approvals
      .filter(a => {
        if (filter !== 'all'     && a.status !== filter)   return false;
        if (teamFilter !== 'all' && a.team !== teamFilter) return false;
        if (riskFilter !== 'all' && a.risk !== riskFilter) return false;
        return true;
      })
      .sort((a, b) => {
        const r = (_RISK_RANK[a.risk] ?? 1) - (_RISK_RANK[b.risk] ?? 1);
        if (r !== 0) return r;
        const s = (_STATUS_RANK[a.status] ?? 1) - (_STATUS_RANK[b.status] ?? 1);
        if (s !== 0) return s;
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
  }, [approvals, filter, teamFilter, riskFilter]);

  const hasActiveFilter = filter !== 'all' || teamFilter !== 'all' || riskFilter !== 'all';
  const allClear = !hasActiveFilter;

  function clearFilters() {
    setFilter('all');
    setTeamFilter('all');
    setRiskFilter('all');
  }
  function toggleStatus(s)  { setFilter(f     => f === s ? 'all' : s); }
  function toggleRisk(r)    { setRiskFilter(rf => rf === r ? 'all' : r); }

  const _HISTORY_RE = /\b(what was|what were|what happened|decided|decision|previous|last\s+\w+|yesterday|history|historical|meeting notes|discussed|agenda|when did|did we|before the|earlier)\b/i;

  async function handleQuery(e) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    const myId = ++requestIdRef.current;
    setBriefLoading(true);
    setBrief(null);
    setHistoryResult(null);
    const isHistory = _HISTORY_RE.test(q);
    setQueryMode(isHistory ? 'history' : 'status');
    if (tweaks && tweaks.navigateToMonitor) tweaks.navigateToMonitor();
    if (isHistory) {
      const result = await window.MOCK_API.askHistory(q);
      if (myId !== requestIdRef.current) return;
      setHistoryResult(result);
    } else {
      const result = await window.MOCK_API.fetchBrief(q);
      if (myId !== requestIdRef.current) return;
      setBrief(result);
    }
    setBriefLoading(false);
    if (tweaks && tweaks.navigateToAttention) tweaks.navigateToAttention();
  }

  function closeDrawer() {
    requestIdRef.current++;
    setBriefLoading(false);
    setBrief(null);
    setHistoryResult(null);
  }

  async function handleAccept(ticket) {
    if (!ticket) return;
    const id = ticket.action_id;
    setResolving(s => ({ ...s, [id]: 'accepting' }));
    if (tweaks && tweaks.activateTrace) tweaks.activateTrace('perform');
    // Open chat panel immediately with empty state — feels instant.
    setChat({ ticket, conversationId: null, state: null });
    try {
      const resp = await window.MOCK_API.acceptAndStart(ticket);
      if (resp && resp.conversation_id) {
        setChat({ ticket, conversationId: resp.conversation_id, state: null });
      } else {
        setChat({ ticket, conversationId: null, state: null, error: resp?.error || 'Failed to start conversation' });
      }
    } finally {
      setResolving(s => { const x = { ...s }; delete x[id]; return x; });
    }
  }

  function handleChatClose(opts) {
    const finalize = opts && opts.finalize;
    if (finalize && chat?.ticket?.action_id) {
      window.MOCK_API.finalizeAccepted(chat.ticket.action_id);
      setApprovals(window.MOCK_API.listApprovals());
    }
    setChat(null);
  }

  async function handleScheduleSync(esc) {
    if (!esc) return;
    setResolving(s => ({ ...s, [esc.action_id]: 'scheduling' }));
    if (tweaks && tweaks.activateTrace) tweaks.activateTrace('perform');
    try {
      await window.MOCK_API.scheduleEscalationSync(esc);
      setApprovals(window.MOCK_API.listApprovals());
    } finally {
      setResolving(s => { const x = { ...s }; delete x[esc.action_id]; return x; });
    }
  }
  function handleReject(id) {
    setResolving(s => ({ ...s, [id]: 'rejected' }));
    if (tweaks && tweaks.activateTrace) tweaks.activateTrace('perform');
    setTimeout(async () => {
      await window.MOCK_API.reject(id);
      setApprovals(window.MOCK_API.listApprovals());
      setResolving(s => { const x = { ...s }; delete x[id]; return x; });
    }, 380);
  }

  return (
    <React.Fragment>
      <div className="standin-query">
        <form className="query-form" onSubmit={handleQuery}>
          <div className="query-input-wrap">
            <span className="query-icon" aria-hidden><Icon name="search" size={15}/></span>
            <input
              ref={queryInputRef}
              className="query-input"
              type="text"
              placeholder="Ask StandIn — e.g. Launch Alpha readiness · what was decided last week?"
              value={query}
              onChange={e => setQuery(e.target.value)}
              disabled={briefLoading}
            />
            {!briefLoading && !query && <kbd className="query-kbd" aria-hidden>/</kbd>}
          </div>
          <button className="btn primary" type="submit" disabled={briefLoading || !query.trim()}>
            {briefLoading ? 'Running…' : 'Get brief'}
          </button>
        </form>
      </div>

      {(briefLoading || brief || historyResult) && (
        <BriefDrawer
          mode={queryMode}
          loading={briefLoading}
          brief={brief}
          historyResult={historyResult}
          onClose={closeDrawer}
        />
      )}

      <div className="page-header">
        <div>
          <h1>
            Attention board
            <span className="live-pulse" title="Polling every 3s"><span/></span>
          </h1>
          <p>Pending approvals, blockers, and conflicts surfaced by the agent network. Review evidence, then resolve or reject.</p>
        </div>
        <div className="toolbar">
          <div className="btn-group" role="group" aria-label="Filter by status">
            {[['all', stats.total], ['blocked', stats.blocked], ['in_review', stats.in_review], ['ready', stats.ready]].map(([s, n]) => (
              <button key={s} className={filter===s?'active':''} onClick={() => setFilter(s)}>
                {s === 'all' ? 'All' : s.replace('_',' ')}
                <span className="btn-count tabular">{n}</span>
              </button>
            ))}
          </div>
          <div className="btn-group" role="group" aria-label="Filter by team">
            {['all', ...window.MOCK_API.TEAMS].map(t => (
              <button key={t} className={teamFilter===t?'active':''} onClick={() => setTeamFilter(t)}>
                {t === 'all' ? 'All teams' : t}
                {t !== 'all' && stats.byTeam[t] > 0 && (
                  <span className="btn-count tabular">{stats.byTeam[t]}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="board">
        {escalation && (
          <div className="escalation pulse" role="alert">
            <div className="escalation-icon">!</div>
            <div className="escalation-body">
              <div className="escalation-title">Escalation Required</div>
              <div className="escalation-text">{escalation.escalation.reason}</div>
              <div className="escalation-meta">recommended → {escalation.escalation.recommended}</div>
            </div>
            <div className="escalation-actions">
              <button
                className="btn primary"
                disabled={!!resolving[escalation.action_id]}
                onClick={() => handleScheduleSync(escalation)}>
                <Icon name="cal" size={14}/>{' '}
                {resolving[escalation.action_id] === 'scheduling' ? 'Scheduling…' : 'Schedule sync'}
              </button>
            </div>
          </div>
        )}

        <div className="board-stats">
          <button
            type="button"
            className={`stat ${allClear ? 'is-current' : ''}`}
            onClick={clearFilters}
            aria-pressed={allClear}
            title={allClear ? 'Showing everything' : 'Clear all filters'}
          >
            <div className="lbl">awaiting you</div>
            <div className="val tabular">{stats.total}</div>
            <div className="delta">{stats.high} high-risk · {stats.blocked} blocked</div>
          </button>
          <button
            type="button"
            className={`stat ${filter === 'blocked' ? 'is-current' : ''}`}
            onClick={() => toggleStatus('blocked')}
            aria-pressed={filter === 'blocked'}
            title="Filter to blocked"
          >
            <div className="lbl">blocked</div>
            <div className="val tabular" style={{ color: 'oklch(0.86 0.10 25)' }}>{stats.blocked}</div>
            <div className="delta">{filter === 'blocked' ? '✓ filtering now' : 'click to filter'}</div>
          </button>
          <button
            type="button"
            className={`stat ${filter === 'in_review' ? 'is-current' : ''}`}
            onClick={() => toggleStatus('in_review')}
            aria-pressed={filter === 'in_review'}
            title="Filter to in review"
          >
            <div className="lbl">in review</div>
            <div className="val tabular" style={{ color: 'oklch(0.92 0.10 80)' }}>{stats.in_review}</div>
            <div className="delta">{filter === 'in_review' ? '✓ filtering now' : 'waiting on humans'}</div>
          </button>
          <button
            type="button"
            className={`stat ${riskFilter === 'high' ? 'is-current' : ''}`}
            onClick={() => toggleRisk('high')}
            aria-pressed={riskFilter === 'high'}
            title="Filter to high risk"
          >
            <div className="lbl">high risk</div>
            <div className="val tabular" style={{ color: 'oklch(0.86 0.10 25)' }}>{stats.high}</div>
            <div className="delta">{riskFilter === 'high' ? '✓ filtering now' : 'surface first'}</div>
          </button>
        </div>

        {hasActiveFilter && (
          <div className="filter-status" role="status">
            <span>
              showing <b className="tabular">{filtered.length}</b> of <span className="tabular">{approvals.length}</span>
              {filter !== 'all'     && <> · status <b>{filter.replace('_',' ')}</b></>}
              {teamFilter !== 'all' && <> · team <b>{teamFilter}</b></>}
              {riskFilter !== 'all' && <> · risk <b>{riskFilter}</b></>}
            </span>
            <button className="filter-clear" onClick={clearFilters}>
              <Icon name="x" size={11}/> clear
            </button>
          </div>
        )}

        <div className="cards">
          {filtered.length === 0 && (
            hasActiveFilter ? (
              <div className="empty">
                <div className="empty-icon"><Icon name="filter" size={22}/></div>
                <div className="big">No matches.</div>
                <div>
                  Nothing matches the current filter.{' '}
                  <button className="link-btn" onClick={clearFilters}>Clear filter</button> to see everything.
                </div>
              </div>
            ) : (
              <div className="empty">
                <div className="empty-icon"><Icon name="check" size={22}/></div>
                <div className="big">All clear.</div>
                <div>No pending items right now. Agents will surface new ones here as they arrive.</div>
              </div>
            )
          )}
          {filtered.map(a => (
            <TicketCard
              key={a.action_id}
              ticket={a}
              state={resolving[a.action_id]}
              onAccept={() => handleAccept(a)}
              onReject={() => handleReject(a.action_id)}
            />
          ))}
        </div>
      </div>

      {chat && (
        <ResolutionChat
          ticket={chat.ticket}
          conversationId={chat.conversationId}
          error={chat.error}
          onClose={handleChatClose}
        />
      )}
    </React.Fragment>
  );
}

function OwnerAvatar({ name, team, size = 36 }) {
  const initials = (name || '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(s => s[0])
    .join('')
    .toUpperCase() || '·';
  const k = TEAM_KEY(team);
  return (
    <div
      className={`owner-avatar team-${k}`}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.36) }}
      aria-label={name}
    >
      {initials}
    </div>
  );
}

function TicketCard({ ticket, state, onAccept, onReject }) {
  const cls = ['ticket-card'];
  if (state === 'accepting') cls.push('resolving');
  if (state === 'rejected')  cls.push('rejected');
  if (ticket.risk === 'high') cls.push('is-high-risk');

  const actionGlyph = {
    send_slack: 'slack',
    send_email: 'mail',
    create_jira: 'jira',
    schedule_meeting: 'cal',
    update_jira_status: 'jira',
  }[ticket.action_type] || 'pulse';

  return (
    <article className={cls.join(' ') + ` team-${ticket.team}`} data-screen-label={`Ticket ${ticket.action_id.slice(0,10)}`}>
      <OwnerAvatar name={ticket.ownerName} team={ticket.team} size={36}/>
      <div className="ticket-body">
        <div className="ticket-head">
          <TeamBadge team={ticket.team}/>
          <StatusPill status={ticket.status}/>
          <RiskBadge risk={ticket.risk}/>
          {ticket.stub && <span className="status-pill stub"><span className="dot"/> stub</span>}
          <span style={{ flex: 1 }}/>
          <span className="id" title={ticket.action_id}>{ticket.action_id.slice(0, 14)}</span>
        </div>
        <div className="ticket-title">
          <Icon name={actionGlyph} size={15} style={{ color: 'var(--fg-2)', flexShrink: 0 }}/>
          <span>{ticket.title}</span>
        </div>
        <div className="ticket-text">{ticket.summary}</div>
        <div className="ticket-meta">
          <span><b>{ticket.ownerName}</b> · {ticket.owner}</span>
          <span>action <b>{ticket.action_type}</b></span>
          <span>opened {relTime(ticket.created_at)}</span>
        </div>
        <PayloadPreview payload={ticket.payload}/>
      </div>
      <div className="ticket-actions">
        <button
          className="btn primary"
          onClick={onAccept}
          disabled={state === 'accepting'}
          aria-label="Accept"
        >
          <Icon name="check" size={14}/>{' '}
          {state === 'accepting' ? 'Accepting…' : 'Accept'}
        </button>
        <button className="btn reject" onClick={onReject} aria-label="Reject">
          Reject
        </button>
      </div>
    </article>
  );
}

function PayloadPreview({ payload }) {
  const [open, setOpen] = useState(false);
  const lines = Object.entries(payload || {});
  if (!lines.length) return null;
  return (
    <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)} className="payload">
      <summary>
        <span className="payload-arrow">{open ? '▾' : '▸'}</span>
        <span className="payload-label">payload_json</span>
        <span className="payload-count">{lines.length} {lines.length === 1 ? 'field' : 'fields'}</span>
      </summary>
      <div className="ticket-payload">
        {lines.map(([k, v]) => (
          <div key={k}><span className="k">"{k}":</span> {JSON.stringify(v)}</div>
        ))}
      </div>
    </details>
  );
}

function BriefDrawer({ mode, loading, brief, historyResult, onClose }) {
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const isHistory = mode === 'history';
  const titleLabel = isHistory ? 'Historical' : 'Status brief';

  return (
    <aside className="brief-drawer" role="dialog" aria-label="Query result">
      <div className="brief-drawer-head">
        <div className="brief-drawer-title">
          <span className={`brief-drawer-mode ${isHistory ? 'history' : 'status'}`}>{titleLabel}</span>
          {loading
            ? <span className="brief-drawer-running"><span className="dot"/> running</span>
            : (brief?.escalation_required && <span className="brief-drawer-tag danger">escalation</span>)}
        </div>
        <button className="brief-drawer-close" onClick={onClose} aria-label="Close (Esc)" title="Close (Esc)">
          <Icon name="x" size={14}/>
        </button>
      </div>
      <div className="brief-drawer-body">
        {loading && <BriefSkeleton mode={mode}/>}
        {!loading && brief && <BriefResult brief={brief}/>}
        {!loading && historyResult && <HistoryResult result={historyResult}/>}
      </div>
    </aside>
  );
}

function BriefSkeleton({ mode }) {
  return (
    <div className="brief-skeleton" aria-busy="true" aria-live="polite">
      <div className="skeleton-meta"/>
      <div className="skeleton-roles">
        {[0, 1, 2].map(i => (
          <div key={i} className="skeleton-role" style={{ animationDelay: `${i * 120}ms` }}>
            <div className="skeleton-row w-30"/>
            <div className="skeleton-row w-90"/>
            <div className="skeleton-row w-70"/>
            <div className="skeleton-row w-50"/>
          </div>
        ))}
      </div>
      <div className="skeleton-status">
        {mode === 'history'
          ? 'Searching knowledge base…'
          : 'Gathering status from all teams — this takes 5–15 seconds…'}
      </div>
    </div>
  );
}

function HistoryResult({ result }) {
  if (!result) return null;
  return (
    <div className="brief-result">
      <div style={{ fontSize: 13, color: 'var(--fg-2)', marginBottom: 10, fontFamily: 'var(--font-mono)' }}>
        historical · {result.retrieval_method}
      </div>
      <p style={{ margin: '0 0 12px', lineHeight: 1.65, color: 'var(--fg-0)' }}>{result.answer}</p>
      {result.source_ids && result.source_ids.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
          {result.source_ids.map(s => (
            <span key={s} className="status-pill stub" style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
              <span className="dot"/> {s}
            </span>
          ))}
        </div>
      )}
      <div className="brief-meta">
        confidence {Math.round((result.confidence || 0) * 100)}%
        {' · '}sources: {result.source_ids?.length ?? 0}
      </div>
    </div>
  );
}

function GX10TrustChip({ gx10 }) {
  const [open, setOpen] = useState(false);
  if (!gx10) return null;
  const skipped     = gx10.status === 'skipped';
  const fields      = gx10.sensitive_fields_redacted || 0;
  const sources     = gx10.redacted_sources || [];
  const sentToCloud = gx10.raw_documents_sent_to_cloud || 0;
  const docs        = gx10.documents_processed || 0;
  const tone = skipped ? 'gx10-skipped' : (fields > 0 ? 'gx10-active' : 'gx10-clean');
  const label = skipped
    ? 'GX10 unreachable — passthrough'
    : fields > 0
      ? `GX10 redacted ${fields} field${fields === 1 ? '' : 's'} across ${sources.length} source${sources.length === 1 ? '' : 's'}`
      : `GX10 verified ${docs} doc${docs === 1 ? '' : 's'} — no redaction needed`;
  return (
    <div className={`gx10-banner ${tone}`}>
      <button className="gx10-chip" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <span className="gx10-shield" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </span>
        <span className="gx10-label">{label}</span>
        <span className="gx10-meta tabular">
          {!skipped && <>edge → cloud: {sentToCloud}/{docs}</>}
        </span>
        <span className="gx10-caret">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="gx10-detail">
          {skipped && (
            <div className="gx10-warn">
              GX10 endpoint was unreachable; documents passed through unredacted.
              Configure <code>GX10_BASE_URL</code> or set <code>GX10_ENABLED=false</code>.
            </div>
          )}
          {!skipped && sources.length === 0 && (
            <div className="gx10-empty">No sensitive fields detected in this batch.</div>
          )}
          {sources.length > 0 && (
            <table className="gx10-table">
              <thead>
                <tr>
                  <th>Source</th><th>Type</th><th>Owner</th>
                  <th className="num">Fields</th><th>Reasons</th>
                </tr>
              </thead>
              <tbody>
                {sources.map(s => (
                  <tr key={s.source_id}>
                    <td className="mono">{s.source_id}</td>
                    <td><span className={`gx10-tag type-${s.source_type}`}>{s.source_type}</span></td>
                    <td>{s.owner}</td>
                    <td className="num tabular">{s.redactions}</td>
                    <td>
                      {(s.reasons || []).map((r, i) => (
                        <span key={i} className="gx10-reason">{r}</span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="gx10-foot">Ran on ASUS GX10 · trust layer {gx10.status}</div>
        </div>
      )}
    </div>
  );
}

function BriefResult({ brief }) {
  const roles = brief.role_statuses || [];
  const passports = brief.evidence_passports || [];
  const redactedSet = new Set((brief.gx10?.redacted_sources || []).map(s => s.source_id));

  return (
    <div className="brief-result">
      <GX10TrustChip gx10={brief.gx10}/>
      {brief.escalation_required && (
        <div className="escalation pulse" role="alert">
          <div className="escalation-icon">!</div>
          <div className="escalation-body">
            <div className="escalation-title">Escalation Required</div>
            <div className="escalation-text">{brief.escalation_reason}</div>
            <div className="escalation-meta">recommended → {brief.recommended_action}</div>
          </div>
        </div>
      )}

      <div className="brief-roles">
        {roles.map(rs => {
          const roleSourceIds = new Set(
            (rs.claims || []).flatMap(c => c.source_ids || [])
          );
          const redactedHere = (brief.gx10?.redacted_sources || [])
            .filter(s => roleSourceIds.has(s.source_id) || (s.owner || '').toLowerCase() === (rs.role || '').toLowerCase());
          const redactedFields = redactedHere.reduce((n, s) => n + (s.redactions || 0), 0);
          return (
          <div key={rs.role} className={`brief-role team-${rs.role}`}>
            <div className="brief-role-head">
              <TeamBadge team={rs.role}/>
              <StatusPill status={rs.status}/>
              <span className="brief-conf">{Math.round((rs.confidence || 0) * 100)}%</span>
              {rs.mode === 'seeded' && <span className="status-pill stub"><span className="dot"/>seeded</span>}
              {redactedFields > 0 && (
                <span
                  className="gx10-source-chip"
                  title={`Redacted by GX10: ${redactedHere.map(s => `${s.source_id} (${s.redactions})`).join(', ')}`}
                >
                  <span className="gx10-shield" aria-hidden="true">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                    </svg>
                  </span>
                  Redacted by GX10 · {redactedFields}
                </span>
              )}
            </div>
            <p className="brief-role-summary">{rs.summary}</p>
            {rs.blockers && rs.blockers.length > 0 && (
              <ul className="brief-blockers">
                {rs.blockers.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            )}
          </div>
          );
        })}
      </div>

      {passports.length > 0 && (
        <details className="brief-passports">
          <summary>Evidence passports ({passports.length})</summary>
          <div className="passport-list">
            {passports.map((p, i) => (
              <div key={i} className="passport-card">
                <div className="passport-claim">{p.claim}</div>
                <div className="passport-meta">
                  <span><b>{p.owner}</b></span>
                  <span>confidence {Math.round((p.confidence || 0) * 100)}%</span>
                  <RiskBadge risk={p.confidence >= 0.85 ? 'low' : p.confidence >= 0.7 ? 'medium' : 'high'}/>
                </div>
                {p.contradictions && p.contradictions.length > 0 && (
                  <div className="passport-contradiction">{p.contradictions[0]}</div>
                )}
              </div>
            ))}
          </div>
        </details>
      )}

      <div className="brief-meta">
        overall confidence {Math.round((brief.overall_confidence || 0) * 100)}%
        {' · '}mode: {brief.mode}
        {brief.delta_claims && brief.delta_claims.length > 0 && (
          <span> · {brief.delta_claims.length} change(s) since last brief</span>
        )}
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Agent-to-agent resolution chat
// ───────────────────────────────────────────────────────────────────────────

const AGENT_META = {
  orchestrator:     { label: 'Our Orchestrator',  short: 'OR', tone: 'orch',     org: 'ours' },
  status_agent:     { label: 'Status Agent',      short: 'ST', tone: 'stat',     org: 'ours' },
  historical_agent: { label: 'Historical Agent',  short: 'HI', tone: 'hist',     org: 'ours' },
  perform_action:   { label: 'Perform Action',    short: 'PA', tone: 'perf',     org: 'ours' },
  watchdog:         { label: 'Watchdog',          short: 'WD', tone: 'watch',    org: 'ours' },
  peer_engineering: { label: 'Engineering · StandIn', short: 'EN', tone: 'peer-eng', org: 'peer' },
  peer_design:      { label: 'Design · StandIn',      short: 'DS', tone: 'peer-des', org: 'peer' },
  peer_gtm:         { label: 'GTM · StandIn',         short: 'GT', tone: 'peer-gtm', org: 'peer' },
  peer_product:     { label: 'Product · StandIn',     short: 'PR', tone: 'peer-prd', org: 'peer' },
};

const KIND_META = {
  handshake: { label: 'handshake', glyph: '↔' },
  delegate:  { label: 'delegate',  glyph: '→' },
  finding:   { label: 'finding',   glyph: '◆' },
  decision:  { label: 'decision',  glyph: '✦' },
  tool_call: { label: 'tool',      glyph: '⚙' },
  completed: { label: 'completed', glyph: '✓' },
  message:   { label: 'message',   glyph: '·' },
};

function _agentMeta(id) {
  return AGENT_META[id] || { label: id || 'unknown', short: (id || '··').slice(0, 2).toUpperCase(), tone: 'orch', org: 'ours' };
}

function ResolutionChat({ ticket, conversationId, error, onClose }) {
  const [state, setState] = useState(null);
  const bodyRef = useRef(null);
  const requestIdRef = useRef(0);

  // Poll backend for conversation state
  useEffect(() => {
    if (!conversationId) return undefined;
    const myId = ++requestIdRef.current;
    let stopped = false;
    let timer = null;

    async function tick() {
      if (stopped || myId !== requestIdRef.current) return;
      const resp = await window.MOCK_API.pollConversation(conversationId);
      if (stopped || myId !== requestIdRef.current) return;
      if (resp) setState(resp);
      const status = resp?.status;
      if (status === 'resolved' || status === 'failed') return; // stop polling
      timer = setTimeout(tick, 1100);
    }
    tick();
    return () => { stopped = true; if (timer) clearTimeout(timer); };
  }, [conversationId]);

  // ESC closes
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose({ finalize: state?.status === 'resolved' }); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, state?.status]);

  // Auto-scroll on new messages
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [state?.messages?.length]);

  const messages    = state?.messages || [];
  const status      = state?.status || (error ? 'failed' : (conversationId ? 'running' : 'starting'));
  const participants = state?.participants || ['orchestrator', 'status_agent', 'perform_action'];
  const isResolved  = status === 'resolved';
  const isFailed    = status === 'failed';

  return (
    <div className="resolve-overlay" role="dialog" aria-label="Agent resolution chat">
      <div className="resolve-backdrop" onClick={() => onClose({ finalize: isResolved })}/>
      <aside className="resolve-panel">
        <header className="resolve-head">
          <div className="resolve-head-meta">
            <span className={`resolve-status-dot ${status}`} aria-hidden/>
            <div>
              <div className="resolve-head-title">
                Agent resolution
                <span className="resolve-head-topic"> · {ticket?.title || ticket?.action_type || 'action'}</span>
              </div>
              <div className="resolve-head-sub">
                {isResolved ? 'agents reached a decision' :
                 isFailed   ? (error || 'conversation failed to start') :
                 conversationId ? 'agents collaborating…' : 'starting…'}
              </div>
            </div>
          </div>
          <button className="resolve-close" onClick={() => onClose({ finalize: isResolved })}
                  aria-label="Close (Esc)" title="Close (Esc)">
            <Icon name="x" size={14}/>
          </button>
        </header>

        <div className="resolve-roster">
          {participants.map(p => {
            const meta = _agentMeta(p);
            const orgCls = meta.org === 'peer' ? 'is-peer' : 'is-ours';
            return (
              <span key={p} className={`resolve-agent-chip tone-${meta.tone} ${orgCls}`}>
                <span className="resolve-agent-mark">{meta.short}</span>
                <span>{meta.label}</span>
              </span>
            );
          })}
        </div>

        <div className="resolve-body" ref={bodyRef}>
          {messages.length === 0 && !isFailed && (
            <ChatThinking who="orchestrator" text="Routing to the right agents…"/>
          )}
          {messages.map(m => (
            <ChatMessage key={m.id} m={m}/>
          ))}
          {!isResolved && !isFailed && messages.length > 0 && (
            <ChatThinking who={_nextSpeaker(messages)} text="thinking…"/>
          )}
          {isFailed && (
            <div className="resolve-error">
              <Icon name="x" size={14}/> {error || 'Agent conversation failed.'}
            </div>
          )}
        </div>

        <footer className="resolve-foot">
          <div className="resolve-foot-meta">
            {messages.length} message{messages.length === 1 ? '' : 's'}
            {state?.action_type && <> · action <b>{state.action_type}</b></>}
            {ticket?.team && <> · team <b>{ticket.team}</b></>}
          </div>
          <div className="resolve-foot-actions">
            {isResolved && (
              <button className="btn primary" onClick={() => onClose({ finalize: true })}>
                <Icon name="check" size={14}/> Done — clear card
              </button>
            )}
            {!isResolved && (
              <button className="btn" onClick={() => onClose({ finalize: false })}>
                Close
              </button>
            )}
          </div>
        </footer>
      </aside>
    </div>
  );
}

function _nextSpeaker(messages) {
  const last = messages[messages.length - 1];
  if (!last) return 'orchestrator';
  // If last was a finding, orchestrator usually speaks next; if delegate, the recipient.
  if (last.kind === 'delegate') return last.recipient || 'status_agent';
  if (last.kind === 'finding')  return 'orchestrator';
  if (last.kind === 'decision') return last.recipient || 'perform_action';
  if (last.kind === 'tool_call') return last.sender || 'perform_action';
  return 'orchestrator';
}

function ChatMessage({ m }) {
  const meta   = _agentMeta(m.sender);
  const target = _agentMeta(m.recipient);
  const kind   = KIND_META[m.kind] || KIND_META.message;
  const isPeer = meta.org === 'peer';
  const cls    = `chat-row tone-${meta.tone}${isPeer ? ' is-peer' : ''}`;
  return (
    <div className={cls}>
      <div className="chat-avatar" title={meta.label}>{meta.short}</div>
      <div className="chat-bubble">
        <div className="chat-bubble-head">
          <span className="chat-from">{meta.label}</span>
          <span className={`chat-org ${isPeer ? 'peer' : ''}`}>{isPeer ? 'peer' : 'ours'}</span>
          <span className="chat-arrow">→</span>
          <span className="chat-to">{target.label}</span>
          <span className={`chat-kind kind-${m.kind}`}>{kind.glyph} {kind.label}</span>
          <span className="chat-time">{_fmtTime(m.ts)}</span>
        </div>
        <div className="chat-content">{m.content}</div>
      </div>
    </div>
  );
}

function ChatThinking({ who, text }) {
  const meta = _agentMeta(who);
  const isPeer = meta.org === 'peer';
  const cls    = `chat-row tone-${meta.tone} thinking${isPeer ? ' is-peer' : ''}`;
  return (
    <div className={cls}>
      <div className="chat-avatar">{meta.short}</div>
      <div className="chat-bubble">
        <div className="chat-bubble-head">
          <span className="chat-from">{meta.label}</span>
          <span className={`chat-org ${isPeer ? 'peer' : ''}`}>{isPeer ? 'peer' : 'ours'}</span>
          <span className="chat-kind kind-thinking">…</span>
        </div>
        <div className="chat-content">
          <span className="chat-typing"><span/><span/><span/></span>
          <span className="chat-typing-text">{text}</span>
        </div>
      </div>
    </div>
  );
}

function _fmtTime(ts) {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch (_) { return ''; }
}

Object.assign(window, { AttentionBoard, BriefResult, ResolutionChat });

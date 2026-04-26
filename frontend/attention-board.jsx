// StandIn — Attention Board view.

const _RISK_RANK   = { high: 0, medium: 1, low: 2 };
const _STATUS_RANK = { blocked: 0, in_review: 1, ready: 2 };

function AttentionBoard({ tweaks }) {
  const [approvals, setApprovals] = useState(() => window.MOCK_API.listApprovals());
  const [resolving, setResolving] = useState({});
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

  function handleResolve(id) {
    setResolving(s => ({ ...s, [id]: 'resolving' }));
    if (tweaks && tweaks.activateTrace) tweaks.activateTrace('perform');
    setTimeout(async () => {
      await window.MOCK_API.approve(id);
      setApprovals(window.MOCK_API.listApprovals());
      setResolving(s => { const x = { ...s }; delete x[id]; return x; });
    }, 380);
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
              <button className="btn primary" onClick={() => handleResolve(escalation.action_id)}>
                <Icon name="cal" size={14}/> Schedule sync
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
              onResolve={() => handleResolve(a.action_id)}
              onReject={() => handleReject(a.action_id)}
            />
          ))}
        </div>
      </div>
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

function TicketCard({ ticket, state, onResolve, onReject }) {
  const cls = ['ticket-card'];
  if (state === 'resolving') cls.push('resolving');
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
        <button className="btn primary" onClick={onResolve} aria-label="Resolve">
          <Icon name="check" size={14}/> Resolve
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

function BriefResult({ brief }) {
  const roles = brief.role_statuses || [];
  const passports = brief.evidence_passports || [];

  return (
    <div className="brief-result">
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
        {roles.map(rs => (
          <div key={rs.role} className={`brief-role team-${rs.role}`}>
            <div className="brief-role-head">
              <TeamBadge team={rs.role}/>
              <StatusPill status={rs.status}/>
              <span className="brief-conf">{Math.round((rs.confidence || 0) * 100)}%</span>
              {rs.mode === 'seeded' && <span className="status-pill stub"><span className="dot"/>seeded</span>}
            </div>
            <p className="brief-role-summary">{rs.summary}</p>
            {rs.blockers && rs.blockers.length > 0 && (
              <ul className="brief-blockers">
                {rs.blockers.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            )}
          </div>
        ))}
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

Object.assign(window, { AttentionBoard, BriefResult });

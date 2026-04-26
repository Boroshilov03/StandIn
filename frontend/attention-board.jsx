// StandIn — Attention Board view.

function AttentionBoard({ tweaks }) {
  const [approvals, setApprovals] = useState(() => window.MOCK_API.listApprovals());
  const [resolving, setResolving] = useState({}); // action_id -> 'resolving' | 'rejected'
  const [filter, setFilter] = useState('all');
  const [teamFilter, setTeamFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [briefLoading, setBriefLoading] = useState(false);
  const [brief, setBrief] = useState(null);
  const [historyResult, setHistoryResult] = useState(null);
  const [queryMode, setQueryMode] = useState('status');

  // Auto-poll every 3s to feel live
  useEffect(() => {
    const t = setInterval(() => setApprovals(window.MOCK_API.listApprovals()), 3000);
    return () => clearInterval(t);
  }, []);

  const escalation = useMemo(() => approvals.find(a => a.escalation && a.escalation.required), [approvals]);

  const stats = useMemo(() => {
    const byStatus = { blocked: 0, in_review: 0, ready: 0 };
    const byRisk = { high: 0, medium: 0, low: 0 };
    approvals.forEach(a => {
      if (byStatus[a.status] !== undefined) byStatus[a.status]++;
      if (byRisk[a.risk] !== undefined) byRisk[a.risk]++;
    });
    return {
      total: approvals.length,
      blocked: byStatus.blocked,
      in_review: byStatus.in_review,
      high: byRisk.high,
    };
  }, [approvals]);

  const filtered = useMemo(() => {
    return approvals.filter(a => {
      if (filter !== 'all' && a.status !== filter) return false;
      if (teamFilter !== 'all' && a.team !== teamFilter) return false;
      return true;
    });
  }, [approvals, filter, teamFilter]);

  const _HISTORY_RE = /\b(what was|what were|what happened|decided|decision|previous|last\s+\w+|yesterday|history|historical|meeting notes|discussed|agenda|when did|did we|before the|earlier)\b/i;

  async function handleQuery(e) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    setBriefLoading(true);
    setBrief(null);
    setHistoryResult(null);
    const isHistory = _HISTORY_RE.test(q);
    setQueryMode(isHistory ? 'history' : 'status');
    // Jump to Orchestration tab so the user can watch the live agent chain
    if (tweaks && tweaks.navigateToMonitor) tweaks.navigateToMonitor();
    if (isHistory) {
      const result = await window.MOCK_API.askHistory(q);
      setHistoryResult(result);
    } else {
      const result = await window.MOCK_API.fetchBrief(q);
      setBrief(result);
    }
    setBriefLoading(false);
    // Return to Attention Board to show the result
    if (tweaks && tweaks.navigateToAttention) tweaks.navigateToAttention();
  }

  function handleResolve(id) {
    setResolving(s => ({ ...s, [id]: 'resolving' }));
    if (tweaks && tweaks.activateTrace) tweaks.activateTrace('perform');
    setTimeout(async () => {
      await window.MOCK_API.approve(id);
      setApprovals(window.MOCK_API.listApprovals());
      setResolving(s => { const x={...s}; delete x[id]; return x; });
    }, 380);
  }
  function handleReject(id) {
    setResolving(s => ({ ...s, [id]: 'rejected' }));
    if (tweaks && tweaks.activateTrace) tweaks.activateTrace('perform');
    setTimeout(async () => {
      await window.MOCK_API.reject(id);
      setApprovals(window.MOCK_API.listApprovals());
      setResolving(s => { const x={...s}; delete x[id]; return x; });
    }, 380);
  }

  return (
    <React.Fragment>
      <div className="standin-query">
        <form className="query-form" onSubmit={handleQuery}>
          <input
            className="query-input"
            type="text"
            placeholder="Ask StandIn — e.g. Launch Alpha readiness · what was decided last week?"
            value={query}
            onChange={e => setQuery(e.target.value)}
            disabled={briefLoading}
          />
          <button className="btn primary" type="submit" disabled={briefLoading || !query.trim()}>
            {briefLoading ? 'Running…' : 'Get brief'}
          </button>
        </form>
        {briefLoading && (
          <div className="query-loading">
            {queryMode === 'history'
              ? 'Searching knowledge base…'
              : 'Gathering status from all teams — this takes 5–15 seconds…'}
          </div>
        )}
        {brief && <BriefResult brief={brief} />}
        {historyResult && <HistoryResult result={historyResult} />}
      </div>

      <div className="page-header">
        <div>
          <h1>Attention board</h1>
          <p>Pending approvals, blockers, and conflicts surfaced by the agent network. Review evidence, then resolve or reject.</p>
        </div>
        <div className="toolbar">
          <div className="btn-group">
            {['all','blocked','in_review','ready'].map(s => (
              <button key={s} className={filter===s?'active':''} onClick={() => setFilter(s)}>
                {s === 'all' ? 'All' : s.replace('_',' ')}
              </button>
            ))}
          </div>
          <div className="btn-group">
            {['all', ...window.MOCK_API.TEAMS].map(t => (
              <button key={t} className={teamFilter===t?'active':''} onClick={() => setTeamFilter(t)}>
                {t === 'all' ? 'All teams' : t}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="board">
        {escalation && (
          <div className="escalation" role="alert">
            <div className="escalation-icon">!</div>
            <div className="escalation-body">
              <div className="escalation-title">Escalation Required</div>
              <div className="escalation-text">{escalation.escalation.reason}</div>
              <div className="escalation-meta">recommended → {escalation.escalation.recommended}</div>
            </div>
            <div className="escalation-actions">
              <button className="btn primary" onClick={() => handleResolve(escalation.action_id)}>
                <Icon name="cal" size={14} /> Schedule sync
              </button>
            </div>
          </div>
        )}

        <div className="board-stats">
          <div className="stat">
            <div className="lbl">awaiting you</div>
            <div className="val tabular">{stats.total}</div>
            <div className="delta">{stats.high} high-risk · {stats.blocked} blocked</div>
          </div>
          <div className="stat"><div className="lbl">blocked</div><div className="val tabular" style={{color:'oklch(0.86 0.10 25)'}}>{stats.blocked}</div><div className="delta">needs resolution</div></div>
          <div className="stat"><div className="lbl">in review</div><div className="val tabular" style={{color:'oklch(0.92 0.10 80)'}}>{stats.in_review}</div><div className="delta">waiting on humans</div></div>
          <div className="stat"><div className="lbl">high risk</div><div className="val tabular" style={{color:'oklch(0.86 0.10 25)'}}>{stats.high}</div><div className="delta">surface first</div></div>
        </div>

        <div className="cards">
          {filtered.length === 0 && (
            <div className="empty">
              <div className="empty-icon">
                <Icon name="check" size={22}/>
              </div>
              <div className="big">All clear.</div>
              <div>No pending items match the current filter. Agents will surface new ones here as they arrive.</div>
            </div>
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

function TicketCard({ ticket, state, onResolve, onReject }) {
  const cls = ['ticket-card'];
  if (state === 'resolving') cls.push('resolving');
  if (state === 'rejected') cls.push('rejected');

  const actionGlyph = {
    send_slack: 'slack',
    send_email: 'mail',
    create_jira: 'jira',
    schedule_meeting: 'cal',
    update_jira_status: 'jira',
  }[ticket.action_type] || 'pulse';

  return (
    <article className={cls.join(' ') + ` team-${ticket.team}`} data-screen-label={`Ticket ${ticket.action_id.slice(0,10)}`}>
      <div>
        <div className="ticket-head">
          <TeamBadge team={ticket.team} />
          <StatusPill status={ticket.status} />
          <RiskBadge risk={ticket.risk} />
          {ticket.stub && <span className="status-pill stub"><span className="dot"/> stub</span>}
          <span style={{flex:1}} />
          <span className="id">{ticket.action_id}</span>
        </div>
        <div className="ticket-title" style={{ display:'flex', alignItems:'center', gap:8 }}>
          <Icon name={actionGlyph} size={15} style={{ color: 'var(--fg-2)' }} />
          {ticket.title}
        </div>
        <div className="ticket-text">{ticket.summary}</div>
        <div className="ticket-meta">
          <span><b>{ticket.ownerName}</b> · {ticket.owner}</span>
          <span>action: <b>{ticket.action_type}</b></span>
          <span>opened {relTime(ticket.created_at)}</span>
        </div>
        <PayloadPreview payload={ticket.payload} />
      </div>
      <div className="ticket-actions">
        <button className="btn primary" onClick={onResolve} aria-label="Resolve">
          <Icon name="check" size={14}/> Resolve
        </button>
        <button className="btn reject" onClick={onReject} aria-label="Reject">
          Reject
        </button>
        <button className="btn ghost" style={{justifyContent:'center'}}>View evidence</button>
      </div>
    </article>
  );
}

function PayloadPreview({ payload }) {
  const [open, setOpen] = useState(false);
  const lines = Object.entries(payload || {});
  if (!lines.length) return null;
  return (
    <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)} style={{ marginTop: 10 }}>
      <summary style={{
        cursor:'pointer', listStyle:'none', fontFamily:'var(--font-mono)',
        fontSize: 11, color:'var(--fg-3)'
      }}>
        {open ? '▾' : '▸'} payload_json
      </summary>
      <div className="ticket-payload">
        {lines.map(([k,v]) => (
          <div key={k}><span className="k">"{k}":</span> {JSON.stringify(v)}</div>
        ))}
      </div>
    </details>
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
        <div className="escalation" role="alert">
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
              <TeamBadge team={rs.role} />
              <StatusPill status={rs.status} />
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
                  <RiskBadge risk={p.confidence >= 0.85 ? 'low' : p.confidence >= 0.7 ? 'medium' : 'high'} />
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

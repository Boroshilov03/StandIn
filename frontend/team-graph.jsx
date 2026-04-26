// StandIn — Team Graph (force-directed). Custom mini-simulator, no external deps.

const TEAM_COLOR = {
  Engineering: 'var(--eng)',
  Design:      'var(--design)',
  GTM:         'var(--gtm)',
  Product:     'var(--product)',
};
const EDGE_STROKE = {
  meeting:      { color: 'oklch(0.72 0.16 245)', dash: '' },
  slack_thread: { color: 'oklch(0.72 0.18 305)', dash: '4 4' },
  jira:         { color: 'oklch(0.74 0.16 55)',  dash: '' },
};
const INTERACTION_COLOR = {
  meeting:      'oklch(0.72 0.16 245)',
  slack_thread: 'oklch(0.72 0.18 305)',
  jira:         'oklch(0.74 0.16 55)',
};

// Pixels from focused user to interaction ring
const RING_R = 148;

function truncLabel(s, max) {
  max = max || 22;
  if (!s) return '';
  return s.length > max ? s.slice(0, max - 1) + '…' : s;
}

// Inline SVG icons for use inside <svg>
function InteractionGlyph({ type, color }) {
  if (type === 'meeting') {
    return (
      <g style={{ pointerEvents: 'none' }} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round">
        <rect x="-9" y="-7" width="18" height="14" rx="2.5"/>
        <line x1="-9" y1="-1.5" x2="9" y2="-1.5"/>
        <line x1="-4" y1="-10" x2="-4" y2="-5"/>
        <line x1="4" y1="-10" x2="4" y2="-5"/>
      </g>
    );
  }
  if (type === 'slack_thread') {
    return (
      <g style={{ pointerEvents: 'none' }} fill="none" stroke={color} strokeWidth="1.7" strokeLinecap="round">
        <line x1="-3" y1="-8" x2="-5.5" y2="8"/>
        <line x1="3.5" y1="-8" x2="1" y2="8"/>
        <line x1="-8.5" y1="-2" x2="8.5" y2="-2"/>
        <line x1="-9" y1="3" x2="7.5" y2="3"/>
      </g>
    );
  }
  return (
    <g style={{ pointerEvents: 'none' }}>
      <text textAnchor="middle" dy="0.38em"
        fontFamily="var(--font-mono)" fontSize="15" fontWeight="800" fill={color}>J</text>
    </g>
  );
}

function TeamGraph({ tweaks }) {
  const [users, setUsers]       = useState(() => window.MOCK_API.listUsers());
  const [edgesAll, setEdgesAll] = useState(() => window.MOCK_API.listEdges());

  useEffect(() => {
    const t = setInterval(() => {
      setUsers(window.MOCK_API.listUsers());
      setEdgesAll(window.MOCK_API.listEdges());
    }, 5000);
    return () => clearInterval(t);
  }, []);

  const connCounts = useMemo(() => {
    const m = {};
    edgesAll.forEach(e => {
      m[e.from_user] = (m[e.from_user] || 0) + 1;
      m[e.to_user]   = (m[e.to_user]   || 0) + 1;
    });
    return m;
  }, [edgesAll]);

  const aggEdges = useMemo(() => {
    const map = new Map();
    edgesAll.forEach(e => {
      const k = [e.from_user, e.to_user].sort().join('|') + '|' + e.type;
      if (!map.has(k)) map.set(k, { ...e, weight: 0, count: 0 });
      const v = map.get(k);
      v.weight += e.weight;
      v.count  += 1;
    });
    return [...map.values()];
  }, [edgesAll]);

  // Selection / focus state
  const [selected, setSelected]         = useState(null);   // drives detail panel
  const [hover, setHover]               = useState(null);
  const [tab, setTab]                   = useState('all');
  const [focusUserId, setFocusUserId]   = useState(null);   // expanded user
  const [focusIntId, setFocusIntId]     = useState(null);   // expanded interaction source_id

  // Auto-select node if requested by Tweaks
  useEffect(() => {
    if (tweaks && tweaks.openNode) {
      clickUser(tweaks.openNode);
      tweaks.clearOpenNode && tweaks.clearOpenNode();
    }
  }, [tweaks && tweaks.openNode]);

  // ESC: collapse interaction → collapse user → deselect
  useEffect(() => {
    function onKey(e) {
      if (e.key !== 'Escape') return;
      if (focusIntId) { setFocusIntId(null); }
      else if (focusUserId) { setFocusUserId(null); setSelected(null); }
      else setSelected(null);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [focusIntId, focusUserId]);

  // Click handlers
  function clickUser(userId) {
    if (userId === focusUserId) {
      setFocusUserId(null);
      setFocusIntId(null);
      setSelected(null);
    } else {
      setFocusUserId(userId);
      setFocusIntId(null);
      setSelected(userId);
    }
  }

  function clickInteraction(int) {
    setFocusIntId(prev => prev === int.source_id ? null : int.source_id);
  }

  function handleBack() {
    if (focusIntId) {
      setFocusIntId(null);
    } else if (focusUserId) {
      setFocusUserId(null);
      setSelected(null);
    }
  }

  // Interactions for the focused user (grouped by source_id)
  const focusInteractions = useMemo(() => {
    if (!focusUserId) return [];
    const iMap = {};
    edgesAll.forEach(e => {
      if (e.from_user !== focusUserId && e.to_user !== focusUserId) return;
      if (!iMap[e.source_id]) iMap[e.source_id] = {
        source_id: e.source_id, label: e.label, type: e.type,
        timestamp: e.timestamp, participants: []
      };
      const other = e.from_user === focusUserId ? e.to_user : e.from_user;
      if (!iMap[e.source_id].participants.includes(other)) iMap[e.source_id].participants.push(other);
    });
    return Object.values(iMap);
  }, [focusUserId, edgesAll]);

  // Participants for the focused interaction
  const focusIntParticipants = useMemo(() => {
    if (!focusIntId) return [];
    const seenIds = new Set();
    const result = [];
    edgesAll.filter(e => e.source_id === focusIntId).forEach(e => {
      [e.from_user, e.to_user].forEach(id => {
        if (!seenIds.has(id)) {
          seenIds.add(id);
          const u = users.find(u => u.id === id);
          if (u) result.push(u);
        }
      });
    });
    return result;
  }, [focusIntId, edgesAll, users]);

  // Simulation
  const stageRef   = useRef(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const dragRef    = useRef(null);
  const panRef     = useRef(null);

  useEffect(() => {
    if (!stageRef.current) return;
    const ro = new ResizeObserver(() => {
      const r = stageRef.current.getBoundingClientRect();
      setSize({ w: r.width, h: r.height });
    });
    ro.observe(stageRef.current);
    return () => ro.disconnect();
  }, []);

  const positions  = useRef({});
  const velocities = useRef({});
  const [, setTick] = useState(0);

  useEffect(() => {
    const cx = size.w/2, cy = size.h/2;
    const teams = ['Engineering','Design','Product','GTM'];
    const byTeam = teams.map(t => users.filter(u => u.team === t));
    let added = false;
    users.forEach(u => {
      if (!positions.current[u.id]) {
        const tIdx      = teams.indexOf(u.team);
        const teamSize  = byTeam[tIdx].length;
        const inner     = byTeam[tIdx].indexOf(u);
        const teamAngle  = (tIdx / teams.length) * Math.PI * 2;
        const innerAngle = (inner / Math.max(1, teamSize)) * Math.PI * 2;
        const baseR  = Math.min(size.w, size.h) * 0.28;
        const innerR = 60;
        positions.current[u.id] = {
          x: cx + Math.cos(teamAngle) * baseR + Math.cos(innerAngle) * innerR,
          y: cy + Math.sin(teamAngle) * baseR + Math.sin(innerAngle) * innerR,
        };
        velocities.current[u.id] = { vx: 0, vy: 0 };
        added = true;
      }
    });
    if (added) setTick(t => t + 1);
  }, [users, size.w, size.h]);

  // Simulation — always runs; no focusMode dependency
  useEffect(() => {
    let raf;
    let alpha = 1;
    function step() {
      alpha *= 0.985;
      const cx = size.w/2, cy = size.h/2;
      const ids = users.map(u => u.id);
      for (let i=0; i<ids.length; i++) {
        for (let j=i+1; j<ids.length; j++) {
          const a = positions.current[ids[i]];
          const b = positions.current[ids[j]];
          if (!a || !b) continue;
          let dx = b.x - a.x, dy = b.y - a.y;
          const d2 = dx*dx + dy*dy + 0.01;
          const d  = Math.sqrt(d2);
          const force = 1800 / d2;
          dx /= d; dy /= d;
          velocities.current[ids[i]].vx -= dx * force * alpha;
          velocities.current[ids[i]].vy -= dy * force * alpha;
          velocities.current[ids[j]].vx += dx * force * alpha;
          velocities.current[ids[j]].vy += dy * force * alpha;
        }
      }
      aggEdges.forEach(e => {
        const a = positions.current[e.from_user];
        const b = positions.current[e.to_user];
        if (!a || !b) return;
        const dx = b.x - a.x, dy = b.y - a.y;
        const d  = Math.sqrt(dx*dx + dy*dy) + 0.01;
        const isFocused = e.from_user === selected || e.to_user === selected;
        const desired = isFocused ? 130 : 170;
        const diff = d - desired;
        const k  = 0.04 * Math.min(2, e.weight) * alpha;
        const fx = (dx / d) * diff * k;
        const fy = (dy / d) * diff * k;
        velocities.current[e.from_user].vx += fx;
        velocities.current[e.from_user].vy += fy;
        velocities.current[e.to_user].vx   -= fx;
        velocities.current[e.to_user].vy   -= fy;
      });
      ids.forEach(id => {
        const p = positions.current[id];
        if (!p) return;
        velocities.current[id].vx += (cx - p.x) * 0.0025 * alpha;
        velocities.current[id].vy += (cy - p.y) * 0.0025 * alpha;
        velocities.current[id].vx *= 0.82;
        velocities.current[id].vy *= 0.82;
        if (dragRef.current?.id !== id) {
          p.x += velocities.current[id].vx;
          p.y += velocities.current[id].vy;
        }
        p.x = Math.max(60, Math.min(size.w - 60, p.x));
        p.y = Math.max(60, Math.min(size.h - 60, p.y));
      });
      setTick(t => t + 1);
      if (alpha > 0.02) raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [users, aggEdges, size.w, size.h, selected]);

  // Opacity helpers
  function edgeOpacity(e) {
    if (focusUserId) return 0.07;
    if (!selected) return hover
      ? (e.from_user === hover || e.to_user === hover ? 0.95 : 0.25)
      : 0.6;
    return e.from_user === selected || e.to_user === selected ? 0.95 : 0.08;
  }

  function nodeOpacity(u) {
    if (!focusUserId) {
      if (!selected) return 1;
      if (u.id === selected) return 1;
      const conn = aggEdges.some(e =>
        (e.from_user === selected && e.to_user === u.id) ||
        (e.to_user === selected && e.from_user === u.id)
      );
      return conn ? 1 : 0.25;
    }
    if (u.id === focusUserId) return 1;
    if (focusIntId) {
      return focusIntParticipants.some(p => p.id === u.id) ? 1 : 0.15;
    }
    const connected = edgesAll.some(e =>
      (e.from_user === focusUserId && e.to_user === u.id) ||
      (e.to_user === focusUserId && e.from_user === u.id)
    );
    return connected ? 0.8 : 0.22;
  }

  // Pan + zoom
  function onWheel(e) {
    e.preventDefault();
    const delta = -e.deltaY * 0.0015;
    setView(v => ({ ...v, k: Math.max(0.5, Math.min(2.4, v.k * (1 + delta))) }));
  }
  function onPointerDown(e) {
    if (e.target.dataset.node) return;
    panRef.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
  }
  function onPointerMove(e) {
    if (panRef.current) {
      setView(v => ({
        ...v,
        x: panRef.current.vx + (e.clientX - panRef.current.x),
        y: panRef.current.vy + (e.clientY - panRef.current.y),
      }));
    }
    if (dragRef.current) {
      const r = stageRef.current.getBoundingClientRect();
      const x = (e.clientX - r.left - view.x) / view.k;
      const y = (e.clientY - r.top  - view.y) / view.k;
      positions.current[dragRef.current.id].x = x;
      positions.current[dragRef.current.id].y = y;
      velocities.current[dragRef.current.id].vx = 0;
      velocities.current[dragRef.current.id].vy = 0;
      setTick(t => t + 1);
    }
  }
  function onPointerUp() { panRef.current = null; dragRef.current = null; }
  function startDrag(e, id) {
    e.stopPropagation();
    dragRef.current = { id };
  }

  // Detail panel data
  const selectedUser          = users.find(u => u.id === selected);
  const selectedEdges         = useMemo(() => selected ? window.MOCK_API.edgesFor(selected) : [], [selected]);
  const filteredSelectedEdges = useMemo(
    () => tab === 'all' ? selectedEdges : selectedEdges.filter(e => e.type === tab),
    [selectedEdges, tab]
  );
  const focusIntData = focusInteractions.find(i => i.source_id === focusIntId) || null;

  // Breadcrumb
  const focusBackLabel = focusIntId
    ? (users.find(u => u.id === focusUserId)?.name?.split(' ')[0] || 'Back')
    : 'All people';
  const focusCrumb = focusIntId
    ? truncLabel(focusIntData?.label, 30)
    : (users.find(u => u.id === focusUserId)?.name || '');

  const hintText = focusUserId
    ? (focusIntId
        ? `${focusIntParticipants.length} participant${focusIntParticipants.length !== 1 ? 's' : ''} · click participant to expand`
        : `${focusInteractions.length} interaction${focusInteractions.length !== 1 ? 's' : ''} · click to expand`)
    : `${users.length} nodes · ${aggEdges.length} edges · drag · scroll to zoom`;

  return (
    <div className="graph-page">
      <div ref={stageRef} className="graph-stage"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <svg>
          <defs>
            <radialGradient id="halo" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.35"/>
              <stop offset="100%" stopColor="currentColor" stopOpacity="0"/>
            </radialGradient>
          </defs>

          <g transform={`translate(${view.x},${view.y}) scale(${view.k})`}>

            {/* ── Background edges ── */}
            {aggEdges.map((e, i) => {
              const a = positions.current[e.from_user];
              const b = positions.current[e.to_user];
              if (!a || !b) return null;
              const stroke = EDGE_STROKE[e.type] || EDGE_STROKE.meeting;
              const w = 0.8 + Math.min(3.6, e.weight * 0.7);
              return (
                <line key={i}
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={stroke.color}
                  strokeWidth={w}
                  strokeDasharray={stroke.dash}
                  strokeLinecap="round"
                  opacity={edgeOpacity(e)}
                  style={{ transition: 'opacity 250ms' }}
                />
              );
            })}

            {/* ── Focus: lines from interaction node to participant user nodes ── */}
            {focusIntId && focusUserId && (() => {
              const userPos = positions.current[focusUserId];
              if (!userPos) return null;
              const intIdx = focusInteractions.findIndex(i => i.source_id === focusIntId);
              if (intIdx < 0) return null;
              const angle = (intIdx / focusInteractions.length) * Math.PI * 2 - Math.PI / 2;
              const intX = userPos.x + Math.cos(angle) * RING_R;
              const intY = userPos.y + Math.sin(angle) * RING_R;
              return focusIntParticipants.map(u => {
                if (u.id === focusUserId) return null;
                const uPos = positions.current[u.id];
                if (!uPos) return null;
                return (
                  <line key={'pl_' + u.id}
                    x1={intX} y1={intY} x2={uPos.x} y2={uPos.y}
                    stroke={TEAM_COLOR[u.team] || 'var(--fg-1)'}
                    strokeWidth="1.5" strokeDasharray="4 3"
                    opacity="0.55" strokeLinecap="round"/>
                );
              });
            })()}

            {/* ── Focus: spoke lines from user node to each interaction node ── */}
            {focusUserId && (() => {
              const userPos = positions.current[focusUserId];
              if (!userPos) return null;
              const n = focusInteractions.length;
              return focusInteractions.map((int, i) => {
                const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
                const x = userPos.x + Math.cos(angle) * RING_R;
                const y = userPos.y + Math.sin(angle) * RING_R;
                const color = INTERACTION_COLOR[int.type];
                const isSel   = int.source_id === focusIntId;
                const isDimmed = focusIntId && !isSel;
                return (
                  <line key={'sl_' + int.source_id}
                    x1={userPos.x} y1={userPos.y} x2={x} y2={y}
                    stroke={color}
                    strokeWidth={isSel ? 1.4 : 0.8}
                    strokeDasharray={isSel ? '' : '5 4'}
                    opacity={isDimmed ? 0.10 : (isSel ? 0.55 : 0.32)}
                    style={{ transition: 'opacity 200ms' }}
                  />
                );
              });
            })()}

            {/* ── User nodes ── */}
            {users.map(u => {
              const p = positions.current[u.id];
              if (!p) return null;
              const isSel   = u.id === selected;
              const isFocUs = u.id === focusUserId;
              const isHover = u.id === hover;
              const r     = isFocUs ? 25 : isSel ? 23 : 17;
              const color = TEAM_COLOR[u.team] || 'var(--fg-1)';
              const cnt   = connCounts[u.id] || 0;
              return (
                <g key={u.id}
                   transform={`translate(${p.x},${p.y})`}
                   style={{ opacity: nodeOpacity(u), transition: 'opacity 220ms', cursor: 'pointer' }}
                   onPointerDown={ev => startDrag(ev, u.id)}
                   onClick={() => clickUser(u.id)}
                   onMouseEnter={() => setHover(u.id)}
                   onMouseLeave={() => setHover(null)}
                >
                  {(isFocUs || isSel || isHover) && (
                    <circle data-node="halo" r={r + 22} fill={color}
                      opacity={isFocUs ? 0.12 : isSel ? 0.09 : 0.055}
                      style={{ filter: 'blur(10px)' }}/>
                  )}
                  {(isFocUs || isSel) && (
                    <circle data-node r={r + 8} fill="none" stroke={color}
                      strokeWidth={isFocUs ? 2 : 1.5}
                      opacity={isFocUs ? 0.45 : 0.35}
                      strokeDasharray={isFocUs ? '' : '3 3'}/>
                  )}
                  <circle data-node r={r + 3} fill="var(--bg-0)" opacity="0.85"/>
                  <circle data-node r={r}
                    fill={`color-mix(in oklch, ${color} ${isFocUs ? 28 : isSel ? 24 : 17}%, oklch(0.195 0.009 60))`}
                    stroke={color}
                    strokeWidth={isFocUs ? 2.8 : isSel ? 2.5 : isHover ? 2 : 1.5}
                    style={{ transition: 'stroke-width 150ms' }}
                  />
                  <text data-node textAnchor="middle" dy="0.34em"
                    fontFamily="var(--font-sans)"
                    fontSize={isFocUs ? 13 : isSel ? 12 : 11}
                    fontWeight="700"
                    fill={isFocUs ? color : isSel ? color : `color-mix(in oklch, ${color} 75%, oklch(0.75 0 0))`}
                    style={{ transition: 'fill 150ms' }}>
                    {initials(u.name)}
                  </text>
                  <text data-node textAnchor="middle" y={r + 17}
                    fontFamily="var(--font-sans)" fontSize="12" fontWeight="500"
                    fill={(isFocUs || isSel) ? 'oklch(0.97 0.004 60)' : 'oklch(0.78 0.006 60)'}
                    letterSpacing="-0.01em"
                    style={{ transition: 'fill 150ms' }}>
                    {u.name}
                  </text>
                  <text data-node textAnchor="middle" y={r + 30}
                    fontFamily="var(--font-mono)" fontSize="10"
                    fill="oklch(0.50 0.009 60)">
                    {u.role}
                  </text>
                  {cnt > 0 && (
                    <g transform={`translate(${r + 1}, ${-r + 1})`}>
                      <circle r="8.5" fill="oklch(0.155 0.008 60)" stroke={color} strokeWidth="1.2"/>
                      <text textAnchor="middle" dy="0.38em"
                        fontSize="8" fontWeight="700" fontFamily="var(--font-mono)"
                        fill={color}>{cnt}</text>
                    </g>
                  )}
                </g>
              );
            })}

            {/* ── Interaction ring nodes (float above user nodes) ── */}
            {focusUserId && (() => {
              const userPos = positions.current[focusUserId];
              if (!userPos) return null;
              const n = focusInteractions.length;
              return focusInteractions.map((int, i) => {
                const angle  = (i / n) * Math.PI * 2 - Math.PI / 2;
                const x      = userPos.x + Math.cos(angle) * RING_R;
                const y      = userPos.y + Math.sin(angle) * RING_R;
                const color  = INTERACTION_COLOR[int.type] || 'var(--fg-2)';
                const isSel  = int.source_id === focusIntId;
                const isDim  = focusIntId && !isSel;
                return (
                  <g key={int.source_id}
                     transform={`translate(${x},${y})`}
                     style={{ cursor: 'pointer', opacity: isDim ? 0.22 : 1, transition: 'opacity 200ms' }}
                     onClick={ev => { ev.stopPropagation(); clickInteraction(int); }}>
                    {isSel && (
                      <circle r="34" fill={color} opacity="0.08" style={{ filter: 'blur(12px)' }}/>
                    )}
                    {isSel && (
                      <circle r="28" fill="none" stroke={color} strokeWidth="1.5" opacity="0.3"
                        strokeDasharray="3 3"/>
                    )}
                    <circle r="22" fill="oklch(0.145 0.008 60)" stroke={color}
                      strokeWidth={isSel ? 2 : 1.6}/>
                    <circle r="19"
                      fill={`color-mix(in oklch, ${color} ${isSel ? 18 : 12}%, oklch(0.195 0.009 60))`}/>
                    <InteractionGlyph type={int.type} color={color}/>
                    <text textAnchor="middle" y="33" fontFamily="var(--font-sans)" fontSize="9.5"
                      fontWeight="500" fill="oklch(0.75 0.006 60)"
                      style={{ pointerEvents: 'none' }}>
                      {truncLabel(int.label, 20)}
                    </text>
                    {!focusIntId && (
                      <text textAnchor="middle" y="43" fontFamily="var(--font-mono)" fontSize="8.5"
                        fill="oklch(0.42 0.009 60)"
                        style={{ pointerEvents: 'none' }}>
                        {int.participants.length}p
                      </text>
                    )}
                  </g>
                );
              });
            })()}
          </g>
        </svg>

        <div className="graph-overlay">
          {focusUserId ? (
            <div className="focus-nav">
              <button className="focus-back-btn" onClick={handleBack}>
                ← {focusBackLabel}
              </button>
              <span className="focus-breadcrumb">{focusCrumb}</span>
            </div>
          ) : (
            <div className="legend">
              <h4>Team</h4>
              {['Engineering','Design','GTM','Product'].map(t => (
                <div key={t} className="legend-team-row">
                  <span className="swatch" style={{ background: TEAM_COLOR[t] }}/> {t}
                </div>
              ))}
              <div className="legend-divider"/>
              <h4>Edge type</h4>
              <div className="legend-row"><div className="legend-line solid meeting"/> Meeting</div>
              <div className="legend-row"><div className="legend-line dashed slack_thread"/> Slack thread</div>
              <div className="legend-row"><div className="legend-line solid jira"/> Jira</div>
            </div>
          )}
        </div>

        <div className="graph-controls">
          <button title="Zoom in"  onClick={() => setView(v => ({ ...v, k: Math.min(2.4, v.k * 1.2) }))}><Icon name="plus"  size={14}/></button>
          <button title="Zoom out" onClick={() => setView(v => ({ ...v, k: Math.max(0.5, v.k / 1.2) }))}><Icon name="minus" size={14}/></button>
          <button title="Reset"    onClick={() => setView({ x:0, y:0, k:1 })}><Icon name="reset" size={14}/></button>
        </div>
        <div className="graph-hint">{hintText}</div>
      </div>

      <aside className="detail">
        {/* Interaction detail panel — level 2 */}
        {focusIntData && (
          <React.Fragment>
            <div className="detail-head"
                 style={{ '--tc': INTERACTION_COLOR[focusIntData.type] }}>
              <div className="detail-avatar" style={{
                background: `color-mix(in oklch, ${INTERACTION_COLOR[focusIntData.type]} 16%, oklch(0.230 0.010 60))`,
                color: INTERACTION_COLOR[focusIntData.type],
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name={focusIntData.type === 'meeting' ? 'cal'
                           : focusIntData.type === 'slack_thread' ? 'slack' : 'jira'} size={22}/>
              </div>
              <div className="name">{truncLabel(focusIntData.label, 44)}</div>
              <div className="role">
                <span className={`type-tag ${focusIntData.type}`}>
                  {focusIntData.type.replace('_', ' ')}
                </span>
              </div>
              <div className="email" style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                {focusIntData.source_id}
              </div>
            </div>
            <div className="detail-tabs">
              <div style={{ padding: '10px 16px', fontSize: 12, color: 'var(--fg-2)', fontWeight: 500 }}>
                Participants ({focusIntParticipants.length})
              </div>
            </div>
            <div className="detail-list">
              {focusIntParticipants.map(u => {
                const uColor = TEAM_COLOR[u.team] || 'var(--fg-1)';
                return (
                  <div key={u.id} className="edge-row"
                       style={{ gridTemplateColumns: '32px 1fr', gap: 12 }}
                       onClick={() => clickUser(u.id)}>
                    <div style={{
                      width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                      background: `color-mix(in oklch, ${uColor} 14%, oklch(0.195 0.009 60))`,
                      border: `1.5px solid ${uColor}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 10, fontWeight: 700, color: uColor,
                      fontFamily: 'var(--font-sans)',
                    }}>
                      {initials(u.name)}
                    </div>
                    <div>
                      <div className="label">{u.name}</div>
                      <div className="who">{u.role} · <TeamBadge team={u.team}/></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </React.Fragment>
        )}

        {/* User detail panel — level 1 / default */}
        {!focusIntData && selectedUser && (
          <React.Fragment>
            <div className="detail-head" style={{ '--tc': TEAM_COLOR[selectedUser.team] }}>
              <div className="detail-avatar">{initials(selectedUser.name)}</div>
              <div className="name">{selectedUser.name}</div>
              <div className="role">
                <TeamBadge team={selectedUser.team}/> · {selectedUser.role}
              </div>
              <div className="email">{selectedUser.email}</div>
            </div>
            <div className="detail-tabs">
              {[
                ['all','All',           selectedEdges.length],
                ['meeting','Meetings',  selectedEdges.filter(e=>e.type==='meeting').length],
                ['slack_thread','Slack',selectedEdges.filter(e=>e.type==='slack_thread').length],
                ['jira','Jira',         selectedEdges.filter(e=>e.type==='jira').length],
              ].map(([k,l,n]) => (
                <button key={k} className={`detail-tab ${tab===k?'active':''}`}
                        onClick={() => setTab(k)}>
                  {l}<span className="count">{n}</span>
                </button>
              ))}
            </div>
            <div className="detail-list">
              {filteredSelectedEdges.length === 0 && (
                <div className="empty" style={{ margin: 16 }}>
                  <div>No {tab === 'all' ? '' : tab.replace('_',' ')} interactions.</div>
                </div>
              )}
              {filteredSelectedEdges.map((e, i) => {
                const otherId = e.from_user === selectedUser.id ? e.to_user : e.from_user;
                const other   = users.find(u => u.id === otherId);
                return (
                  <div key={i} className={`edge-row type-${e.type}`}
                       onClick={() => other && clickUser(other.id)}>
                    <Icon name={e.type === 'meeting' ? 'cal'
                               : e.type === 'slack_thread' ? 'slack' : 'jira'} size={14}
                          style={{ color: EDGE_STROKE[e.type].color }}/>
                    <div>
                      <div className="label">
                        {e.label}
                        <span className={`type-tag ${e.type}`}>
                          {e.type.replace('_',' ').toLowerCase()}
                        </span>
                      </div>
                      <div className="who">with <b>{other ? other.name : otherId}</b></div>
                      <div className="when">
                        {e.timestamp.replace('T',' ').slice(0,16)} UTC · weight {e.weight}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </React.Fragment>
        )}

        {/* Empty state */}
        {!focusIntData && !selectedUser && (
          <div className="detail-empty">
            <div>
              <Icon name="graph" size={28} style={{ color: 'var(--fg-3)', marginBottom: 8 }}/>
              <div style={{ fontSize: 14, color: 'var(--fg-1)', marginBottom: 4 }}>
                Click any node to inspect
              </div>
              <div>
                See connections, meetings, Slack threads, and Jira tickets for that person.
                <br/>Press <span className="key">Esc</span> to deselect.
              </div>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}

function initials(name) {
  return name.split(' ').map(p => p[0]).join('').slice(0,2).toUpperCase();
}

Object.assign(window, { TeamGraph });

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

function TeamGraph({ tweaks }) {
  const users = useMemo(() => window.MOCK_API.listUsers(), []);
  const edgesAll = useMemo(() => window.MOCK_API.listEdges(), []);

  // collapse parallel edges (same pair, same type) into one with summed weight,
  // but keep raw list for the side panel.
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

  const [selected, setSelected] = useState(null);
  const [hover, setHover] = useState(null);
  const [tab, setTab] = useState('all');

  // Auto-select node if requested by Tweaks
  useEffect(() => {
    if (tweaks && tweaks.openNode) {
      setSelected(tweaks.openNode);
      tweaks.clearOpenNode && tweaks.clearOpenNode();
    }
  }, [tweaks && tweaks.openNode]);

  // Simulation
  const stageRef = useRef(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const dragRef = useRef(null);
  const panRef = useRef(null);

  useEffect(() => {
    if (!stageRef.current) return;
    const ro = new ResizeObserver(() => {
      const r = stageRef.current.getBoundingClientRect();
      setSize({ w: r.width, h: r.height });
    });
    ro.observe(stageRef.current);
    return () => ro.disconnect();
  }, []);

  // Position nodes via simple force simulation.
  const positions = useRef({});
  const velocities = useRef({});
  const [, setTick] = useState(0);
  const expanded = !!selected;

  // Initialize positions in concentric layout grouped by team
  useEffect(() => {
    const cx = size.w/2, cy = size.h/2;
    const teams = ['Engineering','Design','Product','GTM'];
    const byTeam = teams.map(t => users.filter(u => u.team === t));
    let added = false;
    users.forEach(u => {
      if (!positions.current[u.id]) {
        const tIdx = teams.indexOf(u.team);
        const teamSize = byTeam[tIdx].length;
        const inner = byTeam[tIdx].indexOf(u);
        const teamAngle = (tIdx / teams.length) * Math.PI * 2;
        const innerAngle = (inner / Math.max(1, teamSize)) * Math.PI * 2;
        const baseR = Math.min(size.w, size.h) * 0.28;
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

  // Simulation tick
  useEffect(() => {
    let raf;
    let alpha = 1;
    const target = aggEdges;
    function step() {
      alpha *= 0.985;
      const cx = size.w/2, cy = size.h/2;
      const ids = users.map(u => u.id);
      // Repulsion
      for (let i=0;i<ids.length;i++) {
        for (let j=i+1;j<ids.length;j++) {
          const a = positions.current[ids[i]];
          const b = positions.current[ids[j]];
          if (!a || !b) continue;
          let dx = b.x - a.x, dy = b.y - a.y;
          let d2 = dx*dx + dy*dy + 0.01;
          let d = Math.sqrt(d2);
          const force = 1800 / d2;
          dx /= d; dy /= d;
          velocities.current[ids[i]].vx -= dx * force * alpha;
          velocities.current[ids[i]].vy -= dy * force * alpha;
          velocities.current[ids[j]].vx += dx * force * alpha;
          velocities.current[ids[j]].vy += dy * force * alpha;
        }
      }
      // Spring
      target.forEach(e => {
        const a = positions.current[e.from_user];
        const b = positions.current[e.to_user];
        if (!a || !b) return;
        const dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.sqrt(dx*dx + dy*dy) + 0.01;
        const desired = expanded && (selected === e.from_user || selected === e.to_user) ? 130 : 170;
        const diff = (d - desired);
        const k = 0.04 * Math.min(2, e.weight) * alpha;
        const fx = (dx / d) * diff * k;
        const fy = (dy / d) * diff * k;
        velocities.current[e.from_user].vx += fx;
        velocities.current[e.from_user].vy += fy;
        velocities.current[e.to_user].vx -= fx;
        velocities.current[e.to_user].vy -= fy;
      });
      // Center gravity
      ids.forEach(id => {
        const p = positions.current[id];
        if (!p) return;
        velocities.current[id].vx += (cx - p.x) * 0.0025 * alpha;
        velocities.current[id].vy += (cy - p.y) * 0.0025 * alpha;
        // Apply
        velocities.current[id].vx *= 0.82;
        velocities.current[id].vy *= 0.82;
        if (dragRef.current?.id !== id) {
          p.x += velocities.current[id].vx;
          p.y += velocities.current[id].vy;
        }
        // Bounds
        p.x = Math.max(60, Math.min(size.w - 60, p.x));
        p.y = Math.max(60, Math.min(size.h - 60, p.y));
      });
      setTick(t => t + 1);
      if (alpha > 0.02) raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [users, aggEdges, size.w, size.h, selected]);

  // Dim non-selected if a node is selected
  function edgeOpacity(e) {
    if (!selected) return hover ? (e.from_user === hover || e.to_user === hover ? 0.95 : 0.25) : 0.6;
    return e.from_user === selected || e.to_user === selected ? 0.95 : 0.08;
  }
  function nodeOpacity(u) {
    if (!selected) return 1;
    if (u.id === selected) return 1;
    const connected = aggEdges.some(e => (e.from_user === selected && e.to_user === u.id) || (e.to_user === selected && e.from_user === u.id));
    return connected ? 1 : 0.25;
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
      setView(v => ({ ...v, x: panRef.current.vx + (e.clientX - panRef.current.x), y: panRef.current.vy + (e.clientY - panRef.current.y) }));
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

  const selectedUser = users.find(u => u.id === selected);
  const selectedEdges = useMemo(() => selected ? window.MOCK_API.edgesFor(selected) : [], [selected]);
  const filteredSelectedEdges = useMemo(() => tab === 'all' ? selectedEdges : selectedEdges.filter(e => e.type === tab), [selectedEdges, tab]);

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
            {/* edges */}
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
                  style={{transition:'opacity 200ms'}}
                />
              );
            })}
            {/* nodes */}
            {users.map(u => {
              const p = positions.current[u.id];
              if (!p) return null;
              const isSel = u.id === selected;
              const isHover = u.id === hover;
              const r = isSel ? 22 : 16;
              const color = TEAM_COLOR[u.team] || 'var(--fg-1)';
              return (
                <g key={u.id}
                   transform={`translate(${p.x},${p.y})`}
                   style={{ opacity: nodeOpacity(u), transition:'opacity 200ms', cursor: 'pointer' }}
                   onPointerDown={(e) => startDrag(e, u.id)}
                   onClick={() => setSelected(u.id === selected ? null : u.id)}
                   onMouseEnter={() => setHover(u.id)}
                   onMouseLeave={() => setHover(null)}
                >
                  {(isSel || isHover) && (
                    <circle data-node="halo" r={r + 18} fill="url(#halo)" style={{ color }} />
                  )}
                  <circle data-node r={r + 4} fill="var(--bg-0)" />
                  <circle data-node r={r}
                    fill={`color-mix(in oklch, ${color} 22%, var(--bg-1))`}
                    stroke={color}
                    strokeWidth={isSel ? 2.2 : 1.4}
                  />
                  <text data-node textAnchor="middle" dy="0.34em"
                    fontFamily="var(--font-sans)" fontSize="11" fontWeight="600"
                    fill={color}>
                    {initials(u.name)}
                  </text>
                  <text data-node textAnchor="middle" y={r + 16}
                    fontFamily="var(--font-sans)" fontSize="12" fontWeight="500"
                    fill="var(--fg-0)" letterSpacing="-0.01em">
                    {u.name}
                  </text>
                  <text data-node textAnchor="middle" y={r + 30}
                    fontFamily="var(--font-mono)" fontSize="10"
                    fill="var(--fg-3)">
                    {u.role}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
        <div className="graph-overlay">
          <div className="legend">
            <h4>Edge type</h4>
            <div className="legend-row"><div className="legend-line solid meeting"/> Meeting</div>
            <div className="legend-row"><div className="legend-line dashed slack_thread"/> Slack thread</div>
            <div className="legend-row"><div className="legend-line solid jira"/> Jira</div>
          </div>
          <div className="legend">
            <h4>Team</h4>
            {['Engineering','Design','GTM','Product'].map(t => (
              <div key={t} className="legend-team-row">
                <span className="swatch" style={{background:TEAM_COLOR[t]}}/> {t}
              </div>
            ))}
          </div>
        </div>
        <div className="graph-controls">
          <button title="Zoom in" onClick={() => setView(v => ({ ...v, k: Math.min(2.4, v.k * 1.2) }))}><Icon name="plus" size={14}/></button>
          <button title="Zoom out" onClick={() => setView(v => ({ ...v, k: Math.max(0.5, v.k / 1.2) }))}><Icon name="minus" size={14}/></button>
          <button title="Reset" onClick={() => setView({x:0,y:0,k:1})}><Icon name="reset" size={14}/></button>
        </div>
        <div className="graph-hint">{aggEdges.length} edges · {users.length} people · drag nodes · scroll to zoom</div>
      </div>

      <aside className="detail">
        {!selectedUser && (
          <div className="detail-empty">
            <div>
              <Icon name="graph" size={28} style={{ color:'var(--fg-3)', marginBottom: 8 }}/>
              <div style={{fontSize:14, color:'var(--fg-1)', marginBottom:4}}>Click any node to inspect</div>
              <div>See connections, meetings, Slack threads, and Jira tickets for that person.<br/>Press <span className="key">Esc</span> to deselect.</div>
            </div>
          </div>
        )}
        {selectedUser && (
          <React.Fragment>
            <div className="detail-head">
              <div className="detail-avatar" style={{color: TEAM_COLOR[selectedUser.team]}}>
                {initials(selectedUser.name)}
              </div>
              <div className="name">{selectedUser.name}</div>
              <div className="role">
                <TeamBadge team={selectedUser.team}/> · {selectedUser.role}
              </div>
              <div className="email">{selectedUser.email}</div>
            </div>
            <div className="detail-tabs">
              {[
                ['all','All', selectedEdges.length],
                ['meeting','Meetings', selectedEdges.filter(e=>e.type==='meeting').length],
                ['slack_thread','Slack', selectedEdges.filter(e=>e.type==='slack_thread').length],
                ['jira','Jira', selectedEdges.filter(e=>e.type==='jira').length],
              ].map(([k,l,n]) => (
                <button key={k} className={`detail-tab ${tab===k?'active':''}`} onClick={() => setTab(k)}>
                  {l}<span className="count">{n}</span>
                </button>
              ))}
            </div>
            <div className="detail-list">
              {filteredSelectedEdges.length === 0 && (
                <div className="empty" style={{margin: 16}}>
                  <div>No {tab === 'all' ? '' : tab.replace('_',' ')} interactions.</div>
                </div>
              )}
              {filteredSelectedEdges.map((e, i) => {
                const otherId = e.from_user === selectedUser.id ? e.to_user : e.from_user;
                const other = users.find(u => u.id === otherId);
                return (
                  <div key={i} className="edge-row" onClick={() => other && setSelected(other.id)} style={{cursor:'pointer'}}>
                    <Icon name={e.type === 'meeting' ? 'cal' : e.type === 'slack_thread' ? 'slack' : 'jira'} size={14}
                          style={{color: EDGE_STROKE[e.type].color}}/>
                    <div>
                      <div className="label">
                        {e.label}
                        <span className={`type-tag ${e.type}`}>{e.type.replace('_',' ').toLowerCase()}</span>
                      </div>
                      <div className="who">with <b>{other ? other.name : otherId}</b></div>
                      <div className="when">{e.timestamp.replace('T',' ').slice(0,16)} UTC · weight {e.weight}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </React.Fragment>
        )}
      </aside>
    </div>
  );
}

function initials(name) {
  return name.split(' ').map(p => p[0]).join('').slice(0,2).toUpperCase();
}

Object.assign(window, { TeamGraph });

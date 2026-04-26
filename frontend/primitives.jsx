// StandIn — shared UI primitives.
export const TEAM_KEY = (t) => (t || '').toLowerCase();
export const TEAM_VAR = {
  engineering: 'var(--eng)',
  design:      'var(--design)',
  gtm:         'var(--gtm)',
  product:     'var(--product)',
};

export function Icon({ name, size = 16, style }) {
  const s = { width: size, height: size, ...style };
  const sw = 1.6;
  const props = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: sw, strokeLinecap: 'round', strokeLinejoin: 'round', style: s };
  switch (name) {
    case 'inbox': return <svg {...props}><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"/></svg>;
    case 'graph': return <svg {...props}><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8 7l3 9M16 7l-3 9M8 6h8"/></svg>;
    case 'pulse': return <svg {...props}><path d="M3 12h4l2-7 4 14 2-7h6"/></svg>;
    case 'check': return <svg {...props}><path d="M20 6 9 17l-5-5"/></svg>;
    case 'x':     return <svg {...props}><path d="M18 6 6 18M6 6l12 12"/></svg>;
    case 'alert': return <svg {...props}><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4"/><circle cx="12" cy="17" r="0.5" fill="currentColor"/></svg>;
    case 'mail':  return <svg {...props}><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>;
    case 'slack': return <svg {...props}><rect x="3" y="10" width="8" height="3" rx="1.5"/><rect x="13" y="10" width="8" height="3" rx="1.5"/><rect x="10" y="3" width="3" height="8" rx="1.5"/><rect x="10" y="13" width="3" height="8" rx="1.5"/></svg>;
    case 'jira':  return <svg {...props}><path d="M11 3h10v10a4 4 0 0 1-4 4M13 21H3V11a4 4 0 0 1 4-4"/></svg>;
    case 'cal':   return <svg {...props}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/></svg>;
    case 'plus':  return <svg {...props}><path d="M12 5v14M5 12h14"/></svg>;
    case 'minus': return <svg {...props}><path d="M5 12h14"/></svg>;
    case 'reset': return <svg {...props}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>;
    case 'search':return <svg {...props}><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>;
    case 'filter':return <svg {...props}><path d="M3 5h18l-7 9v6l-4-2v-4Z"/></svg>;
    default: return null;
  }
}

export function TeamBadge({ team, dot = true }) {
  const k = TEAM_KEY(team);
  return (
    <span className={`team-badge ${k}`}>
      {dot && <span className="swatch" />}
      {team}
    </span>
  );
}

export function StatusPill({ status }) {
  const label = (status || '').replace('_', ' ');
  return <span className={`status-pill ${status}`}><span className="dot" /> {label}</span>;
}

export function RiskBadge({ risk }) {
  return <span className={`risk ${risk}`}>{(risk || '').toUpperCase()}</span>;
}

export function relTime(iso) {
  const d = new Date(iso);
  const now = Date.now();
  const diff = (now - d.getTime()) / 1000;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff/60)}m ago`;
  if (diff < 86400) return `${Math.round(diff/3600)}h ago`;
  return d.toISOString().slice(0,10);
}

export function timeOnly(iso) {
  return new Date(iso).toISOString().slice(11,19);
}


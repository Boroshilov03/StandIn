// StandIn — Premium marketing landing page
import { useEffect, useRef, useState } from 'react';
import './landing.css';

// ─── Animated mesh canvas ───────────────────────────────────────────────────
function MeshBackground() {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let raf, t = 0;

    const nodes = Array.from({ length: 36 }, () => ({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.00025,
      vy: (Math.random() - 0.5) * 0.00025,
      r: Math.random() * 1.8 + 0.8,
      phase: Math.random() * Math.PI * 2,
    }));

    function resize() {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    }

    function draw() {
      const W = canvas.width, H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      t += 0.006;
      nodes.forEach(n => {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > 1) n.vx *= -1;
        if (n.y < 0 || n.y > 1) n.vy *= -1;
      });
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          const dx = (a.x - b.x) * W, dy = (a.y - b.y) * H;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < 200) {
            ctx.strokeStyle = `rgba(130, 100, 255, ${(1 - d / 200) * 0.18})`;
            ctx.lineWidth = 0.6;
            ctx.beginPath();
            ctx.moveTo(a.x * W, a.y * H);
            ctx.lineTo(b.x * W, b.y * H);
            ctx.stroke();
          }
        }
      }
      nodes.forEach(n => {
        const p = Math.sin(t + n.phase) * 0.5 + 0.5;
        ctx.fillStyle = `rgba(120, 90, 255, ${0.25 + p * 0.35})`;
        ctx.beginPath();
        ctx.arc(n.x * W, n.y * H, n.r * (1 + p * 0.4), 0, Math.PI * 2);
        ctx.fill();
      });
      raf = requestAnimationFrame(draw);
    }

    resize();
    draw();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, []);
  return <canvas ref={ref} className="lp-mesh" aria-hidden="true" />;
}

// ─── Animated terminal ───────────────────────────────────────────────────────
const TERM_LINES = [
  { delay: 0,    kind: 'input',   text: '"Give me a briefing on Launch Alpha readiness."' },
  { delay: 600,  kind: 'info',    label: 'intent',   text: 'briefing_request · teams: [eng, design, gtm]' },
  { delay: 1100, kind: 'ok',      label: 'route',    text: 'status_agent:8007 · gather phase started' },
  { delay: 1800, kind: 'ok',      label: 'synthesise', text: '3 role reports · parallel Gemini calls' },
  { delay: 2400, kind: 'warn',    label: 'conflict', text: 'design:ready ✕ engineering:blocked (NOVA-142)' },
  { delay: 3000, kind: 'danger',  label: 'escalate', text: 'checkout API /v1→/v2 · escalation_required: true' },
  { delay: 3600, kind: 'ok',      label: 'passport', text: 'evidence generated · confidence: high' },
];

function Terminal() {
  const [visible, setVisible] = useState(0);
  useEffect(() => {
    const timers = TERM_LINES.map((l, i) =>
      setTimeout(() => setVisible(v => Math.max(v, i + 1)), l.delay)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="lp-terminal" aria-label="Agent pipeline trace">
      <div className="lp-term-bar">
        <span className="lp-term-dot r" /><span className="lp-term-dot y" /><span className="lp-term-dot g" />
        <span className="lp-term-title">standin · orchestrator · live</span>
      </div>
      <div className="lp-term-body">
        {TERM_LINES.slice(0, visible).map((l, i) => (
          <div key={i} className={`lp-tl lp-tl-${l.kind}`}>
            {l.kind === 'input'
              ? <><span className="lp-tl-arrow">›</span><span className="lp-tl-input">{l.text}</span></>
              : <><span className={`lp-tl-tag lp-tl-tag-${l.kind}`}>{l.label}</span><span className="lp-tl-text">{l.text}</span></>
            }
          </div>
        ))}
        {visible < TERM_LINES.length && <div className="lp-term-cursor" />}
      </div>
    </div>
  );
}

// ─── Scroll-reveal wrapper ───────────────────────────────────────────────────
function Reveal({ children, className = '', delay = 0 }) {
  const ref = useRef(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setOn(true); obs.disconnect(); }
    }, { threshold: 0.12 });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return (
    <div
      ref={ref}
      className={`lp-reveal ${on ? 'lp-reveal-in' : ''} ${className}`}
      style={{ transitionDelay: on ? `${delay}ms` : '0ms' }}
    >
      {children}
    </div>
  );
}

// ─── Agent cards ─────────────────────────────────────────────────────────────
const AGENTS = [
  {
    id: 'orchestrator', name: 'Orchestrator',    port: ':8000',
    role: 'Intent classification + routing',
    note: 'Entry point. Classifies every message into one of 5 intent types and routes to the correct agent.',
    colorVar: '--lp-indigo', icon: '◈',
  },
  {
    id: 'status',       name: 'Status Agent',    port: ':8007',
    role: 'Gather · Synthesise · Contradict',
    note: 'Pulls from Slack, Jira, Calendar — runs parallel Gemini synthesis — fires conflict engine.',
    colorVar: '--lp-teal', icon: '◎',
  },
  {
    id: 'historical',   name: 'Historical Agent', port: ':8009',
    role: 'Three-tier RAG retrieval',
    note: 'Atlas Vector Search → BM25 keyword → Gemini synthesis. 25-document corpus. No configuration needed.',
    colorVar: '--lp-purple', icon: '◷',
  },
  {
    id: 'perform',      name: 'Perform Action',   port: ':8008',
    role: '8 action types + approval gate',
    note: 'Executes or queues actions. Human approval required for send_email, send_slack, schedule_meeting.',
    colorVar: '--lp-amber', icon: '◆',
  },
  {
    id: 'watchdog',     name: 'Watchdog Agent',   port: ':8010',
    role: 'Proactive monitoring + alerts',
    note: 'Polls Status Agent every 30 minutes. Detects status deltas and fires draft_slack alerts automatically.',
    colorVar: '--lp-rose', icon: '◉',
  },
];

// ─── Main landing component ──────────────────────────────────────────────────
export function LandingPage({ onEnterDashboard }) {
  const agentRef = useRef(null);

  function scrollToAgents() {
    agentRef.current?.scrollIntoView({ behavior: 'smooth' });
  }

  return (
    <div className="lp">

      {/* ════════════════════ HERO ════════════════════ */}
      <section className="lp-hero">
        <MeshBackground />
        <div className="lp-hero-glow" aria-hidden="true" />
        <div className="lp-hero-inner">
          <div className="lp-hero-left">
            <div className="lp-eyebrow">
              <span className="lp-eyebrow-dot" />
              Multi-agent AI coordination platform
            </div>
            <h1 className="lp-h1">
              Stop attending<br />
              <span className="lp-h1-accent">meetings.</span><br />
              Send your StandIn.
            </h1>
            <p className="lp-hero-sub">
              A network of AI agents that gathers status from Slack, Jira, and Calendar —
              detects blockers and contradictions across teams in real time —
              and routes every action through a human approval gate.
              All traceable. All auditable.
            </p>
            <div className="lp-hero-ctas">
              <button className="lp-btn-primary" onClick={onEnterDashboard}>
                Open dashboard
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
              <button className="lp-btn-ghost" onClick={scrollToAgents}>
                See agent network
              </button>
            </div>
            <div className="lp-hero-stats">
              <div className="lp-stat">
                <span className="lp-stat-n">5</span>
                <span className="lp-stat-l">specialized agents</span>
              </div>
              <span className="lp-stat-sep" />
              <div className="lp-stat">
                <span className="lp-stat-n">8</span>
                <span className="lp-stat-l">action types</span>
              </div>
              <span className="lp-stat-sep" />
              <div className="lp-stat">
                <span className="lp-stat-n">3</span>
                <span className="lp-stat-l">retrieval tiers</span>
              </div>
              <span className="lp-stat-sep" />
              <div className="lp-stat">
                <span className="lp-stat-n">0</span>
                <span className="lp-stat-l">meetings attended</span>
              </div>
            </div>
          </div>
          <div className="lp-hero-right">
            <Terminal />
          </div>
        </div>
        <div className="lp-hero-scroll-hint" onClick={scrollToAgents} aria-label="Scroll down">
          <div className="lp-scroll-line" />
        </div>
      </section>

      {/* ════════════════════ AGENT NETWORK ════════════════════ */}
      <section className="lp-section" ref={agentRef} id="agent-network">
        <div className="lp-section-inner">
          <Reveal>
            <div className="lp-section-eyebrow">Agent network</div>
            <h2 className="lp-h2">Five agents. One coordinated intelligence.</h2>
            <p className="lp-section-sub">
              Each agent owns a domain. Communication happens via the Fetch.ai uAgents Chat Protocol
              and is registered on Agentverse — discoverable through ASI:One.
            </p>
          </Reveal>

          <div className="lp-agents-grid">
            {AGENTS.map((a, i) => (
              <Reveal key={a.id} delay={i * 80}>
                <div className="lp-agent-card" style={{ '--agent-color': `var(${a.colorVar})` }}>
                  <div className="lp-ac-top">
                    <span className="lp-ac-icon">{a.icon}</span>
                    <span className="lp-ac-port">{a.port}</span>
                  </div>
                  <div className="lp-ac-name">{a.name}</div>
                  <div className="lp-ac-role">{a.role}</div>
                  <div className="lp-ac-note">{a.note}</div>
                </div>
              </Reveal>
            ))}
          </div>

          {/* Intent routing table */}
          <Reveal delay={100}>
            <div className="lp-intent-table">
              <div className="lp-intent-table-head">
                <span>Intent</span><span>Routes to</span><span>Example</span>
              </div>
              {[
                { n: '01', name: 'Status query',      route: 'Status Agent',    ex: '"What is engineering working on?"' },
                { n: '02', name: 'Conflict check',    route: 'Status Agent',    ex: '"Is GTM aligned with engineering on the launch date?"' },
                { n: '03', name: 'Action request',    route: 'Perform Action',  ex: '"Schedule a call between Alice and Carol."' },
                { n: '04', name: 'History query',     route: 'Historical Agent',ex: '"What was decided in last week\'s launch sync?"' },
                { n: '05', name: 'Briefing request',  route: 'Status Agent',    ex: '"Give me a morning brief."' },
              ].map(r => (
                <div key={r.n} className="lp-intent-row">
                  <span className="lp-ir-n">{r.n}</span>
                  <span className="lp-ir-name">{r.name}</span>
                  <span className="lp-ir-arrow">→</span>
                  <span className="lp-ir-route">{r.route}</span>
                  <span className="lp-ir-ex">{r.ex}</span>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* ════════════════════ EVIDENCE PASSPORT ════════════════════ */}
      <section className="lp-section lp-section-alt">
        <div className="lp-section-inner lp-two-col">
          <Reveal className="lp-col-text">
            <div className="lp-section-eyebrow">Evidence Passports</div>
            <h2 className="lp-h2">Every claim is sourced.<br />Every risk is flagged.</h2>
            <p className="lp-section-sub">
              StandIn doesn't just summarize — it generates a traceable Evidence Passport
              for every assertion. Source, owner, timestamp, confidence, contradictions,
              recommended action. Not a chatbot. An audit trail.
            </p>
            <ul className="lp-feat-list">
              <li>Source-linked to Slack, Jira, or Calendar events</li>
              <li>Confidence levels: high · medium · low</li>
              <li>Contradictions surfaced across all team reports</li>
              <li>Escalation flag triggers the human approval gate</li>
            </ul>
          </Reveal>
          <Reveal className="lp-col-visual" delay={120}>
            <div className="lp-passport">
              <div className="lp-pp-header">
                <div className="lp-pp-icon-wrap">
                  <span className="lp-pp-icon">◉</span>
                </div>
                <div>
                  <div className="lp-pp-title">Evidence Passport</div>
                  <div className="lp-pp-sub">NOVA-142 · Launch Alpha</div>
                </div>
                <span className="lp-pp-badge danger">ESCALATE</span>
              </div>
              <div className="lp-pp-body">
                {[
                  { k: 'claim',    v: '"Launch page is final and ready to ship."', mono: false },
                  { k: 'source',   v: 'slack:#design-final · 2026-04-25T14:32Z',  mono: true  },
                  { k: 'owner',    v: 'Priya Mehta · Design',                      mono: false },
                  { k: 'confidence', v: null, conf: 'high' },
                  { k: 'contradictions', v: 'NOVA-142: checkout API /v1→/v2 · Engineering blocked', danger: true },
                  { k: 'recommended', v: 'Schedule 15-min escalation: Design + Engineering only', mono: false },
                  { k: 'escalation_required', v: 'true', danger: true },
                ].map((f, i) => (
                  <div key={i} className={`lp-pp-field ${f.danger ? 'lp-pp-field-danger' : ''}`}>
                    <span className="lp-pp-key">{f.k}</span>
                    {f.conf
                      ? <span className="lp-pp-conf ok">{f.conf}</span>
                      : <span className={`lp-pp-val ${f.mono ? 'mono' : ''} ${f.danger ? 'danger-text' : ''}`}>{f.v}</span>
                    }
                  </div>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ════════════════════ CONFLICT DETECTION ════════════════════ */}
      <section className="lp-section">
        <div className="lp-section-inner">
          <Reveal>
            <div className="lp-section-eyebrow">Conflict detection</div>
            <h2 className="lp-h2">Contradictions across teams —<br />caught instantly.</h2>
            <p className="lp-section-sub">
              The Status Agent runs a deterministic rule engine on every response.
              LLM enrichment is optional — rules are authoritative. No model can suppress
              an escalation.
            </p>
          </Reveal>
          <Reveal delay={80}>
            <div className="lp-conflict">
              <div className="lp-cf-card ok">
                <div className="lp-cf-header">
                  <span className="lp-cf-team design">Design</span>
                  <span className="lp-cf-src">slack:#design-final</span>
                </div>
                <div className="lp-cf-status ok-text">ready</div>
                <div className="lp-cf-quote">"Launch page is final and ready to ship."</div>
                <div className="lp-cf-meta">Priya Mehta · Apr 25, 14:32</div>
              </div>
              <div className="lp-cf-vs">
                <div className="lp-cf-bolt">✕</div>
                <div className="lp-cf-vslabel">conflict detected</div>
                <div className="lp-cf-rule">rule engine · deterministic</div>
              </div>
              <div className="lp-cf-card danger">
                <div className="lp-cf-header">
                  <span className="lp-cf-team eng">Engineering</span>
                  <span className="lp-cf-src">jira:NOVA-142</span>
                </div>
                <div className="lp-cf-status danger-text">blocked</div>
                <div className="lp-cf-quote">"Checkout API changed /v1→/v2 last night — this is a blocker."</div>
                <div className="lp-cf-meta">Derek Vasquez · Apr 25, 22:14</div>
              </div>
            </div>
          </Reveal>
          <Reveal delay={140}>
            <div className="lp-cf-outcome">
              <span className="lp-cf-outcome-dot" />
              <span>
                <b>escalation_required: true</b> ·
                Recommendation: schedule 15-min escalation sync · Design + Engineering only ·
                do not include GTM or Product until API surface is resolved.
              </span>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ════════════════════ HUMAN APPROVAL ════════════════════ */}
      <section className="lp-section lp-section-alt">
        <div className="lp-section-inner lp-two-col lp-two-col-rev">
          <Reveal className="lp-col-visual" delay={120}>
            <div className="lp-approval">
              <div className="lp-ap-header">
                <div className="lp-ap-status-dot warn" />
                <div className="lp-ap-meta">
                  <div className="lp-ap-title">Pending Human Approval</div>
                  <div className="lp-ap-sub">schedule_meeting · requested 2 min ago</div>
                </div>
              </div>
              <div className="lp-ap-body">
                {[
                  { label: 'Action type',   val: 'schedule_meeting' },
                  { label: 'Parties',       val: 'Priya Mehta, Derek Vasquez' },
                  { label: 'Subject',       val: 'NOVA-142 escalation — checkout API /v1→/v2' },
                  { label: 'Duration',      val: '15 minutes' },
                  { label: 'Requested by',  val: 'StandIn Orchestrator' },
                ].map(f => (
                  <div key={f.label} className="lp-ap-field">
                    <span className="lp-ap-key">{f.label}</span>
                    <span className="lp-ap-val">{f.val}</span>
                  </div>
                ))}
              </div>
              <div className="lp-ap-actions">
                <button className="lp-ap-btn approve" disabled>Approve &amp; execute</button>
                <button className="lp-ap-btn reject" disabled>Reject</button>
              </div>
            </div>
          </Reveal>
          <Reveal className="lp-col-text">
            <div className="lp-section-eyebrow">Human approval gate</div>
            <h2 className="lp-h2">Agents propose.<br />Humans decide.</h2>
            <p className="lp-section-sub">
              High-stakes actions are never executed autonomously. StandIn queues them
              for explicit human approval — via dashboard, REST API, or any external surface.
            </p>
            <div className="lp-action-table">
              <div className="lp-at-row">
                <span className="lp-at-badge danger">Approval required</span>
                <span className="lp-at-items">send_email · send_slack · schedule_meeting</span>
              </div>
              <div className="lp-at-row">
                <span className="lp-at-badge ok">Auto-execute</span>
                <span className="lp-at-items">create_jira · draft_slack · create_action_item · update_jira_status · post_brief</span>
              </div>
            </div>
            <ul className="lp-feat-list" style={{ marginTop: '1.5rem' }}>
              <li>All decisions written to an immutable action log</li>
              <li>REST API: GET /approvals · POST /approve · POST /reject</li>
              <li>Approval graph visible in Team Graph dashboard tab</li>
            </ul>
          </Reveal>
        </div>
      </section>

      {/* ════════════════════ ORCHESTRATION TRACE ════════════════════ */}
      <section className="lp-section">
        <div className="lp-section-inner">
          <Reveal>
            <div className="lp-section-eyebrow">Orchestration trace</div>
            <h2 className="lp-h2">Full pipeline visibility.<br />Every hop logged.</h2>
            <p className="lp-section-sub">
              The Orchestration Monitor shows every message hop in real time.
              See intent classification, routing decisions, agent responses,
              synthesis steps, escalations — all in a live feed.
            </p>
          </Reveal>
          <Reveal delay={60}>
            <div className="lp-trace">
              {[
                { step: '01', label: 'User message',       detail: '"Give me a briefing on Launch Alpha readiness."',       color: 'var(--fg-2)',     kind: '' },
                { step: '02', label: 'Orchestrator',       detail: 'intent: briefing_request · teams: [eng, design, gtm]', color: 'var(--lp-indigo)', kind: '' },
                { step: '03', label: 'Status Agent',       detail: 'Gather phase — Slack, Jira, Calendar (parallel)',       color: 'var(--lp-teal)',   kind: '' },
                { step: '04', label: 'Gemini synthesis',   detail: '3 role reports · synthesis per team in parallel',       color: 'var(--lp-teal)',   kind: '' },
                { step: '05', label: 'Conflict engine',    detail: 'design:ready ✕ engineering:blocked — rule fired',       color: 'var(--lp-amber)',  kind: 'warn' },
                { step: '06', label: 'Evidence Passport',  detail: 'escalation_required: true · confidence: high',          color: 'var(--lp-rose)',   kind: 'danger' },
                { step: '07', label: 'Response delivered', detail: 'Brief + passport + recommendation sent to user',        color: 'var(--lp-teal)',   kind: 'ok' },
              ].map((s, i, arr) => (
                <div key={s.step} className={`lp-trace-step ${s.kind}`}>
                  <div className="lp-ts-spine">
                    <div className="lp-ts-dot" style={{ background: s.color, boxShadow: `0 0 10px ${s.color}66` }} />
                    {i < arr.length - 1 && <div className="lp-ts-line" />}
                  </div>
                  <div className="lp-ts-content">
                    <span className="lp-ts-step" style={{ color: s.color }}>{s.step}</span>
                    <span className="lp-ts-label">{s.label}</span>
                    <span className="lp-ts-detail">{s.detail}</span>
                  </div>
                </div>
              ))}
            </div>
          </Reveal>
          <Reveal delay={120}>
            <div className="lp-trace-cta">
              <button className="lp-btn-primary" onClick={onEnterDashboard}>
                Open Orchestration Monitor
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ════════════════════ FOOTER CTA ════════════════════ */}
      <section className="lp-footer-cta">
        <div className="lp-fc-glow" aria-hidden="true" />
        <div className="lp-fc-inner">
          <Reveal>
            <div className="lp-fc-label">Built at LA Hacks 2026</div>
            <h2 className="lp-fc-title">
              Your team has a meeting problem.<br />
              <span className="lp-h1-accent">StandIn</span> has the fix.
            </h2>
            <button className="lp-btn-primary lp-btn-xl" onClick={onEnterDashboard}>
              Open dashboard
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
            <div className="lp-fc-stack">
              Fetch.ai uAgents · Google Gemini 2.5 Flash · MongoDB Atlas Vector Search · ElevenLabs
            </div>
          </Reveal>
        </div>
      </section>
    </div>
  );
}

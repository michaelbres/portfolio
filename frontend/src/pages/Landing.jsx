// /home/user/portfolio/frontend/src/pages/Landing.jsx
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'

// ── Data pills ────────────────────────────────────────────────────────────────

function Pill({ children }) {
  return <span className="data-pill">{children}</span>
}

// ── Accent label ──────────────────────────────────────────────────────────────

function AccentLabel({ color = 'electric', children, dot = false }) {
  const palettes = {
    electric: { bg: 'rgba(0,102,204,0.08)',    text: '#0066CC', dot: '#0066CC' },
    emerald:  { bg: 'rgba(40,205,65,0.08)',    text: '#1D9E35', dot: '#28CD41' },
    amethyst: { bg: 'rgba(168,85,247,0.08)',   text: '#9333EA', dot: '#A855F7' },
    mist:     { bg: 'rgba(134,134,139,0.08)',  text: '#86868B', dot: '#86868B' },
  }
  const p = palettes[color] ?? palettes.electric
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
      style={{ background: p.bg, color: p.text }}
    >
      {dot && (
        <span
          className="w-1.5 h-1.5 rounded-full inline-block animate-pulse-slow"
          style={{ background: p.dot }}
        />
      )}
      {children}
    </span>
  )
}

// ── CTA link ─────────────────────────────────────────────────────────────────

function CtaLink({ color = '#0066CC', children }) {
  return (
    <span
      className="inline-flex items-center gap-1 text-sm font-medium transition-opacity duration-200 hover:opacity-70"
      style={{ color }}
    >
      {children} <span aria-hidden="true" style={{ fontSize: '0.85em' }}>›</span>
    </span>
  )
}

// ── Tile 1 — MLB Fair Value (hero: col-span-2 row-span-2) ────────────────────

function FairValueTile() {
  return (
    <Link
      to="/sports/mlb/fair-value"
      className="bento-tile glow-electric block relative col-span-2 row-span-2 p-7 flex flex-col justify-between min-h-[300px] group"
      style={{ textDecoration: 'none' }}
    >
      {/* Background lambda decoration */}
      <span
        aria-hidden="true"
        className="absolute bottom-4 right-7 select-none pointer-events-none text-[9rem] font-thin leading-none"
        style={{ color: 'rgba(0,102,204,0.05)', fontFamily: 'Georgia, serif' }}
      >
        λ
      </span>

      {/* Top */}
      <div className="flex flex-col gap-3 relative z-10">
        <AccentLabel color="electric" dot>MLB · Fair Value</AccentLabel>

        <h2
          className="text-snow leading-tight"
          style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}
        >
          MLB Fair Value Model
        </h2>
        <p className="text-mist text-sm leading-relaxed max-w-md">
          xFIP-powered win probabilities. NegBin run distribution, team defense,
          weather carry, Platt calibration. Compare fair odds against Kalshi closing lines.
        </p>

        {/* Data pills */}
        <div className="flex flex-wrap gap-2 mt-1">
          <Pill>NegBin r=3.0</Pill>
          <Pill>xFIP vs Kalshi</Pill>
          <Pill>72h fatigue</Pill>
          <Pill>Platt scaling</Pill>
        </div>
      </div>

      {/* CTA */}
      <div className="relative z-10 mt-6">
        <CtaLink color="#0066CC">View Today's Odds</CtaLink>
      </div>
    </Link>
  )
}

// ── Tile 2 — Statcast Analytics (row-span-2) ─────────────────────────────────

function StatcastTile() {
  return (
    <Link
      to="/sports/mlb"
      className="bento-tile glow-electric block relative p-7 flex flex-col justify-between min-h-[300px] group"
      style={{ textDecoration: 'none' }}
    >
      <div className="flex flex-col gap-3">
        <AccentLabel color="electric">Statcast</AccentLabel>

        <h2
          className="text-snow leading-tight"
          style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.02em' }}
        >
          Pitch Analytics
        </h2>
        <p className="text-mist text-sm leading-relaxed">
          500k+ pitch events. wOBA splits, movement profiles, Stuff+ modeling.
        </p>
        <div className="flex flex-wrap gap-2 mt-1">
          <Pill>wOBA splits</Pill>
          <Pill>Stuff+</Pill>
          <Pill>IVB / HB</Pill>
        </div>
      </div>

      <div className="mt-4">
        <CtaLink color="#0066CC">Explore Pitchers</CtaLink>
      </div>
    </Link>
  )
}

// ── Tile 3 — Betting Tools ───────────────────────────────────────────────────

function BettingTile() {
  return (
    <Link
      to="/betting"
      className="bento-tile glow-emerald block relative p-6 flex flex-col justify-between group"
      style={{ textDecoration: 'none' }}
    >
      <div className="flex flex-col gap-2.5">
        <AccentLabel color="emerald">Tools</AccentLabel>

        <h2
          className="text-snow leading-tight"
          style={{ fontSize: '1.1rem', fontWeight: 700, letterSpacing: '-0.02em' }}
        >
          Betting Tools
        </h2>
        <p className="text-mist text-sm leading-relaxed">
          No-vig odds, Kelly criterion, EV calculator, parlay builder.
        </p>
      </div>
      <div className="mt-5">
        <CtaLink color="#1D9E35">Open Tools</CtaLink>
      </div>
    </Link>
  )
}

// ── Tile 4 — Model Architecture ──────────────────────────────────────────────

function ModelTile() {
  return (
    <Link
      to="/sports/mlb/fair-value"
      className="bento-tile glow-amethyst block relative p-6 flex flex-col justify-between group"
      style={{ textDecoration: 'none' }}
    >
      <div className="flex flex-col gap-2.5">
        <AccentLabel color="amethyst">Models</AccentLabel>

        <h2
          className="text-snow leading-tight"
          style={{ fontSize: '1.1rem', fontWeight: 700, letterSpacing: '-0.02em' }}
        >
          Model Architecture
        </h2>

        {/* Formula block */}
        <div
          className="mt-1.5 rounded-2xl px-3.5 py-3 font-mono text-xs leading-relaxed"
          style={{
            background: 'rgba(168,85,247,0.06)',
            border: '1px solid rgba(168,85,247,0.12)',
            color: '#9333EA',
          }}
        >
          λ = offense × xFIP<br />
          {'  '}× defense × PF × HFA
        </div>
      </div>
      <div className="mt-5">
        <CtaLink color="#9333EA">Read More</CtaLink>
      </div>
    </Link>
  )
}

// ── Tile 5 — Coming Soon ─────────────────────────────────────────────────────

function ComingSoonTile() {
  return (
    <div className="bento-tile block relative p-6 flex flex-col justify-between">
      <div className="flex flex-col gap-2.5">
        <AccentLabel color="mist">Soon</AccentLabel>

        <h2
          className="text-mist leading-tight"
          style={{ fontSize: '1.1rem', fontWeight: 600, letterSpacing: '-0.02em' }}
        >
          NFL · NBA · Trading Bots
        </h2>
        <p className="text-mist text-sm leading-relaxed" style={{ opacity: 0.6 }}>
          More projects in development.
        </p>
      </div>
      <div className="mt-5 flex gap-1.5">
        {['NFL', 'NBA', 'Quant'].map((tag) => (
          <span
            key={tag}
            className="text-[10px] font-medium px-2.5 py-0.5 rounded-full"
            style={{
              background: 'rgba(134,134,139,0.08)',
              color: '#86868B',
              border: '1px solid rgba(134,134,139,0.12)',
            }}
          >
            {tag}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Landing() {
  return (
    <div className="mesh-bg min-h-screen">
      <Navbar />

      <main className="max-w-5xl mx-auto px-6 pt-24 pb-28">

        {/* ── Hero ───────────────────────────────────────────────────────── */}
        <header className="mb-20 flex flex-col items-center text-center gap-5">

          {/* Location tag */}
          <span
            className="inline-flex items-center gap-1.5 text-xs font-medium tracking-widest uppercase px-3 py-1 rounded-full"
            style={{
              background: 'rgba(0,0,0,0.04)',
              border: '1px solid rgba(0,0,0,0.08)',
              color: '#86868B',
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: '#28CD41' }}
            />
            Boston, MA
          </span>

          {/* Name — large, bold, tight */}
          <h1
            className="text-snow font-display leading-none"
            style={{
              fontSize: 'clamp(3rem, 9vw, 6.5rem)',
              fontWeight: 700,
              letterSpacing: '-0.03em',
            }}
          >
            Michael Breslow
          </h1>

          {/* Subtitle — lighter, for contrast */}
          <p
            className="text-mist max-w-md"
            style={{
              fontSize: 'clamp(1rem, 2.5vw, 1.25rem)',
              fontWeight: 400,
              letterSpacing: '0.01em',
              lineHeight: 1.5,
            }}
          >
            Analytics Engineer &middot; Sports &middot; Markets &middot; Models
          </p>
        </header>

        {/* ── Bento Grid ─────────────────────────────────────────────────── */}
        {/*
          Desktop (3-col):
            [FairValue ×2 ×2] [Statcast ×1 ×2]
            [Betting]         [Model]            [Soon]
        */}
        <div
          className="grid grid-cols-1 md:grid-cols-3 gap-4"
          style={{ gridAutoRows: 'minmax(140px, auto)' }}
        >
          <div className="md:col-span-2 md:row-span-2">
            <FairValueTile />
          </div>
          <div className="md:row-span-2">
            <StatcastTile />
          </div>

          <BettingTile />
          <ModelTile />
          <ComingSoonTile />
        </div>
      </main>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
        <div className="max-w-5xl mx-auto px-6 py-8 flex items-center justify-between gap-4">
          <span
            className="text-mist text-sm font-medium"
            style={{ letterSpacing: '-0.01em' }}
          >
            Michael Breslow
          </span>
          <a
            href="https://github.com/michaelbres"
            target="_blank"
            rel="noopener noreferrer"
            className="text-mist text-sm transition-colors duration-200 hover:text-snow"
            style={{ letterSpacing: '-0.01em' }}
          >
            github.com/michaelbres
          </a>
        </div>
      </footer>
    </div>
  )
}

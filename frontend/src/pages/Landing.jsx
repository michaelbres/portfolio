// /home/user/portfolio/frontend/src/pages/Landing.jsx
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'

// ── Data pills ────────────────────────────────────────────────────────────────

function Pill({ children }) {
  return <span className="data-pill">{children}</span>
}

// ── Bento tiles ───────────────────────────────────────────────────────────────

// Tile 1 — MLB Fair Value (hero tile, col-span-2 row-span-2)
function FairValueTile() {
  return (
    <Link
      to="/sports/mlb/fair-value"
      className="bento-tile glow-electric block relative col-span-2 row-span-2 p-6 flex flex-col justify-between min-h-[280px] group"
      style={{ textDecoration: 'none' }}
    >
      {/* Background lambda decoration */}
      <span
        aria-hidden="true"
        className="absolute bottom-4 right-6 select-none pointer-events-none text-[9rem] font-thin leading-none animate-pulse-slow"
        style={{ color: 'rgba(14,165,233,0.07)', fontFamily: 'Georgia, serif' }}
      >
        λ
      </span>

      {/* Top section */}
      <div className="flex flex-col gap-3 relative z-10">
        {/* Accent label */}
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
            style={{ background: 'rgba(14,165,233,0.15)', color: '#0EA5E9' }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-electric animate-pulse inline-block" />
            MLB · Fair Value
          </span>
        </div>

        <h2 className="text-snow text-2xl font-semibold leading-tight tracking-tight">
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
      <div className="relative z-10 mt-6 flex items-center gap-2">
        <span
          className="text-sm font-medium px-4 py-2 rounded-xl transition-all duration-200"
          style={{
            background: 'rgba(14,165,233,0.15)',
            color: '#0EA5E9',
            border: '1px solid rgba(14,165,233,0.25)',
          }}
        >
          View Today's Odds →
        </span>
      </div>
    </Link>
  )
}

// Tile 2 — Statcast Analytics (row-span-2)
function StatcastTile() {
  return (
    <Link
      to="/sports/mlb"
      className="bento-tile glow-electric block relative p-6 flex flex-col justify-between min-h-[280px] group"
      style={{ textDecoration: 'none' }}
    >
      {/* Top */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
            style={{ background: 'rgba(14,165,233,0.12)', color: '#38BDF8' }}
          >
            Statcast
          </span>
        </div>
        <h2 className="text-snow text-xl font-semibold leading-tight tracking-tight">
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

      {/* CTA */}
      <div className="mt-4">
        <span
          className="text-xs font-medium"
          style={{ color: '#38BDF8' }}
        >
          Explore Pitchers →
        </span>
      </div>
    </Link>
  )
}

// Tile 3 — Betting Tools (1 col)
function BettingTile() {
  return (
    <Link
      to="/betting"
      className="bento-tile glow-emerald block relative p-5 flex flex-col justify-between group"
      style={{ textDecoration: 'none' }}
    >
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
            style={{ background: 'rgba(16,185,129,0.12)', color: '#10B981' }}
          >
            Tools
          </span>
        </div>
        <h2 className="text-snow text-lg font-semibold leading-tight tracking-tight">
          Betting Tools
        </h2>
        <p className="text-mist text-sm leading-relaxed">
          No-vig odds, Kelly criterion, EV calculator, parlay builder.
        </p>
      </div>
      <div className="mt-4">
        <span className="text-xs font-medium" style={{ color: '#10B981' }}>
          Open Tools →
        </span>
      </div>
    </Link>
  )
}

// Tile 4 — Model Architecture (1 col)
function ModelTile() {
  return (
    <Link
      to="/sports/mlb/fair-value"
      className="bento-tile glow-amethyst block relative p-5 flex flex-col justify-between group"
      style={{ textDecoration: 'none' }}
    >
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
            style={{ background: 'rgba(168,85,247,0.12)', color: '#A855F7' }}
          >
            Models
          </span>
        </div>
        <h2 className="text-snow text-lg font-semibold leading-tight tracking-tight">
          Model Architecture
        </h2>

        {/* Formula block */}
        <div
          className="mt-2 rounded-xl px-3 py-2.5 font-mono text-xs leading-relaxed"
          style={{
            background: 'rgba(168,85,247,0.08)',
            border: '1px solid rgba(168,85,247,0.15)',
            color: '#C084FC',
          }}
        >
          λ = offense × xFIP<br />
          {'  '}× defense × PF × HFA
        </div>
      </div>
      <div className="mt-4">
        <span className="text-xs font-medium" style={{ color: '#A855F7' }}>
          Read More →
        </span>
      </div>
    </Link>
  )
}

// Tile 5 — Coming Soon (1 col)
function ComingSoonTile() {
  return (
    <div
      className="bento-tile block relative p-5 flex flex-col justify-between"
      style={{ background: '#1C1C1E', opacity: 0.85 }}
    >
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
            style={{ background: 'rgba(134,134,139,0.12)', color: '#86868B' }}
          >
            Soon
          </span>
        </div>
        <h2 className="text-mist text-lg font-semibold leading-tight tracking-tight">
          NFL · NBA · Trading Bots
        </h2>
        <p className="text-mist text-sm leading-relaxed" style={{ opacity: 0.6 }}>
          More projects in development.
        </p>
      </div>
      <div className="mt-4 flex gap-1.5">
        {['NFL', 'NBA', 'Quant'].map((tag) => (
          <span
            key={tag}
            className="text-[10px] font-medium px-2 py-0.5 rounded-full"
            style={{
              background: 'rgba(134,134,139,0.10)',
              color: '#86868B',
              border: '1px solid rgba(134,134,139,0.15)',
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

      <main className="max-w-6xl mx-auto px-5 pt-20 pb-24">

        {/* ── Hero ────────────────────────────────────────────────────── */}
        <header className="mb-16 flex flex-col gap-4">
          {/* Location tag */}
          <span
            className="inline-flex items-center gap-1.5 text-xs font-medium tracking-widest uppercase self-start px-3 py-1 rounded-full"
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.10)',
              color: '#86868B',
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: '#10B981' }}
            />
            Boston, MA
          </span>

          {/* Name */}
          <h1
            className="text-snow font-display leading-none tracking-tight"
            style={{
              fontSize: 'clamp(3rem, 9vw, 7rem)',
              fontWeight: 300,
              letterSpacing: '-0.02em',
            }}
          >
            Michael Breslow
          </h1>

          {/* Subtitle */}
          <p
            className="text-mist text-lg font-light tracking-wide"
            style={{ letterSpacing: '0.04em' }}
          >
            Analytics Engineer &middot; Sports &middot; Markets &middot; Models
          </p>
        </header>

        {/* ── Bento Grid ──────────────────────────────────────────────── */}
        {/*
          Desktop: 3-col grid. Tiles:
            [FairValue x2 x2] [Statcast x1 x2]
            (implicit from row-span-2 above)
            [Betting x1]      [Model x1]       [ComingSoon x1]
        */}
        <div
          className="grid grid-cols-1 md:grid-cols-3 gap-4"
          style={{ gridAutoRows: 'minmax(140px, auto)' }}
        >
          {/* Row 1 + 2: FairValue (col 1-2, row 1-2) + Statcast (col 3, row 1-2) */}
          <div className="md:col-span-2 md:row-span-2">
            <FairValueTile />
          </div>
          <div className="md:row-span-2">
            <StatcastTile />
          </div>

          {/* Row 3: Betting, Model, ComingSoon */}
          <BettingTile />
          <ModelTile />
          <ComingSoonTile />
        </div>
      </main>

      {/* ── Footer ──────────────────────────────────────────────────── */}
      <footer
        className="border-t"
        style={{ borderColor: 'rgba(255,255,255,0.06)' }}
      >
        <div className="max-w-6xl mx-auto px-5 py-8 flex items-center justify-between gap-4">
          <span className="text-mist text-sm font-medium tracking-tight">
            Michael Breslow
          </span>
          <a
            href="https://github.com/michaelbres"
            target="_blank"
            rel="noopener noreferrer"
            className="text-mist hover:text-snow text-sm transition-colors duration-150"
          >
            github.com/michaelbres
          </a>
        </div>
      </footer>
    </div>
  )
}

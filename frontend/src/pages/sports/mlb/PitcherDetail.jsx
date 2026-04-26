import { useState, useEffect, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, LineChart, Line,
} from 'recharts'
import Navbar from '../../../components/Navbar'
import PageHeader from '../../../components/PageHeader'
import PitchLocationChart from '../../../components/mlb/PitchLocationChart'
import PitchMovementChart from '../../../components/mlb/PitchMovementChart'
import LeaderboardTable from '../../../components/mlb/LeaderboardTable'
import { mlb } from '../../../lib/api'
import { pitchColor, PITCH_LABEL } from '../../../lib/pitchColors'
import { savantColor } from '../../../lib/savantColor'

const TABS = ['Overview', 'Arsenal', 'Location', 'Movement', 'Pitch Log']

const PITCH_LOG_COLS = [
  { key: 'game_date',     label: 'Date' },
  { key: 'pitch_name',    label: 'Pitch' },
  { key: 'release_speed', label: 'Velo',  format: (v) => v?.toFixed(1) },
  { key: 'release_spin_rate', label: 'Spin', format: (v) => v ? Math.round(v) : '–' },
  { key: 'pfx_x',         label: 'HB"',   format: (v) => v != null ? (v * 12).toFixed(1) : '–' },
  { key: 'pfx_z',         label: 'IVB"',  format: (v) => v != null ? (v * 12).toFixed(1) : '–' },
  { key: 'plate_x',       label: 'pX',    format: (v) => v?.toFixed(2) },
  { key: 'plate_z',       label: 'pZ',    format: (v) => v?.toFixed(2) },
  { key: 'balls',         label: 'B' },
  { key: 'strikes',       label: 'S' },
  { key: 'description',   label: 'Result' },
  { key: 'events',        label: 'Event' },
  { key: 'launch_speed',  label: 'EV',    format: (v) => v?.toFixed(1) },
  { key: 'launch_angle',  label: 'LA',    format: (v) => v?.toFixed(1) },
  { key: 'estimated_woba_using_speedangle', label: 'xwOBA', format: (v) => v?.toFixed(3) },
]

const cardStyle = {
  background: '#FFFFFF',
  border: '1px solid rgba(0,0,0,0.08)',
  borderRadius: '14px',
}

// ── Savant-style headshot URL builder ────────────────────────────────────────
// Uses MLB's official headshot CDN. Falls back to a gray silhouette on error.
function headshotUrl(pitcherId) {
  return `https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/${pitcherId}/headshot/67/current`
}

export default function PitcherDetail() {
  const { id } = useParams()
  const pitcherId = Number(id)
  const [tab, setTab] = useState(0)
  const [summary, setSummary] = useState(null)
  const [pitches, setPitches] = useState([])
  const [loading, setLoading] = useState(true)
  const [season, setSeason] = useState(2025)
  const [selectedPitchType, setSelectedPitchType] = useState('')
  const [logOffset, setLogOffset] = useState(0)
  const [logTotal, setLogTotal] = useState(0)

  // Percentile data from league-wide pitching leaderboard
  const [leaderboard, setLeaderboard] = useState([])

  useEffect(() => {
    setLoading(true)
    Promise.all([
      mlb.pitcherSummary(id, { season }),
      mlb.pitcherPitches(id, { season, limit: 2000 }),
      mlb.leaderboardPitching({ season, min_pitches: 100 }).catch(() => ({ data: [] })),
    ])
      .then(([sumRes, pitchRes, lbRes]) => {
        setSummary(sumRes.data)
        setPitches(pitchRes.data.data)
        setLogTotal(pitchRes.data.total)
        setLeaderboard(lbRes.data || [])
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [id, season])

  const filteredPitches = selectedPitchType
    ? pitches.filter((p) => p.pitch_type === selectedPitchType)
    : pitches

  // Compute percentile ranks for this pitcher across key metrics
  const percentiles = useMemo(() => {
    if (!leaderboard.length) return null
    const self = leaderboard.find((r) => r.pitcher_id === pitcherId)
    if (!self) return null

    const pct = (key, higherIsBetter = true) => {
      const vals = leaderboard.map((r) => r[key]).filter((v) => v != null).sort((a, b) => a - b)
      if (!vals.length || self[key] == null) return null
      const val = self[key]
      let below = 0
      for (const v of vals) { if (v < val) below++ }
      const p = below / vals.length
      return higherIsBetter ? p : 1 - p
    }

    return [
      { label: 'Fastball Velo', key: 'avg_velo',          raw: self.avg_velo,          pct: pct('avg_velo'),           fmt: (v) => v?.toFixed(1) + ' mph' },
      { label: 'Max Velo',      key: 'max_velo',          raw: self.max_velo,          pct: pct('max_velo'),           fmt: (v) => v?.toFixed(1) + ' mph' },
      { label: 'Spin Rate',     key: 'avg_spin',          raw: self.avg_spin,          pct: pct('avg_spin'),           fmt: (v) => v ? Math.round(v) + ' rpm' : '–' },
      { label: 'Extension',     key: 'avg_extension',     raw: self.avg_extension,     pct: pct('avg_extension'),      fmt: (v) => v?.toFixed(1) + ' ft' },
      { label: 'IVB',           key: 'avg_pfx_z',         raw: self.avg_pfx_z,         pct: pct('avg_pfx_z'),          fmt: (v) => v != null ? (v * 12).toFixed(1) + '"' : '–' },
      { label: 'Whiff %',       key: 'whiff_rate',        raw: self.whiff_rate,        pct: pct('whiff_rate'),         fmt: (v) => v != null ? v.toFixed(1) + '%' : '–' },
      { label: 'xwOBA Against', key: 'avg_xwoba_against', raw: self.avg_xwoba_against, pct: pct('avg_xwoba_against', false), fmt: (v) => v?.toFixed(3) },
    ].filter((p) => p.pct != null)
  }, [leaderboard, pitcherId])

  if (loading) {
    return (
      <div className="min-h-screen" style={{ background: '#F5F5F7' }}>
        <Navbar />
        <div className="flex items-center justify-center h-64 animate-pulse" style={{ color: '#86868B' }}>
          Loading pitcher data…
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="min-h-screen" style={{ background: '#F5F5F7' }}>
        <Navbar />
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <div style={{ color: '#86868B' }}>Pitcher not found.</div>
          <Link to="/sports/mlb" className="text-sm hover:underline" style={{ color: '#0066CC' }}>
            ← Back to MLB
          </Link>
        </div>
      </div>
    )
  }

  const handIcon = summary.p_throws === 'R' ? 'RHP' : summary.p_throws === 'L' ? 'LHP' : '–'

  return (
    <div className="min-h-screen" style={{ background: '#F5F5F7' }}>
      <Navbar />

      {/* Savant-style profile header: headshot + name + meta + percentile bars */}
      <div style={{ background: '#FFFFFF', borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center gap-2 text-xs mb-4" style={{ color: '#86868B' }}>
            <Link to="/sports/mlb" className="hover:opacity-70 transition-opacity" style={{ color: '#86868B' }}>MLB</Link>
            <span>›</span>
            <Link to="/sports/mlb" className="hover:opacity-70 transition-opacity" style={{ color: '#86868B' }}>Pitching Leaderboard</Link>
            <span>›</span>
            <span style={{ color: '#1D1D1F' }}>{summary.pitcher_name}</span>
          </div>

          <div className="flex flex-wrap items-start gap-6">
            <div
              className="flex-shrink-0 rounded-full overflow-hidden"
              style={{
                width: 108, height: 108,
                background: '#E8E8ED',
                border: '2px solid rgba(0,0,0,0.08)',
              }}
            >
              <img
                src={headshotUrl(pitcherId)}
                alt={summary.pitcher_name}
                width={108}
                height={108}
                onError={(e) => { e.target.style.display = 'none' }}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </div>

            <div className="flex-1 min-w-0">
              <h1
                className="tracking-tight"
                style={{
                  fontWeight: 600,
                  fontSize: 'clamp(1.75rem, 3vw, 2.25rem)',
                  color: '#1D1D1F',
                  letterSpacing: '-0.02em',
                  lineHeight: 1.1,
                }}
              >
                {summary.pitcher_name}
              </h1>
              <div className="flex flex-wrap items-center gap-3 mt-2">
                <span
                  className="text-[11px] font-semibold uppercase tracking-widest px-2.5 py-1 rounded-full"
                  style={{ background: 'rgba(0,102,204,0.10)', color: '#0066CC' }}
                >
                  {handIcon}
                </span>
                <span className="text-sm" style={{ color: '#86868B' }}>
                  {summary.total_pitches?.toLocaleString()} pitches · {season} season
                </span>
              </div>
            </div>

            <div className="flex-shrink-0">
              <select
                value={season}
                onChange={(e) => setSeason(Number(e.target.value))}
                style={{
                  background: '#FFFFFF',
                  border: '1px solid rgba(0,0,0,0.12)',
                  color: '#1D1D1F',
                  borderRadius: 980,
                  padding: '0.4rem 0.9rem',
                  fontSize: '0.875rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                <option value={2026}>2026</option>
                <option value={2025}>2025</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Tabs */}
        <div
          className="flex gap-1 mb-6 p-1 rounded-full overflow-x-auto"
          style={{ background: '#E8E8ED', width: 'fit-content' }}
        >
          {TABS.map((t, i) => (
            <button
              key={t}
              onClick={() => setTab(i)}
              className="px-4 py-1.5 text-sm rounded-full transition-all duration-150 font-medium whitespace-nowrap"
              style={
                tab === i
                  ? { background: '#FFFFFF', color: '#1D1D1F', boxShadow: '0 1px 2px rgba(0,0,0,0.08)' }
                  : { background: 'transparent', color: '#86868B' }
              }
            >
              {t}
            </button>
          ))}
        </div>

        {/* Pitch type filter pills (Location + Movement only) */}
        {(tab === 2 || tab === 3) && (
          <div className="flex flex-wrap gap-2 mb-4">
            <PitchPill
              active={selectedPitchType === ''}
              onClick={() => setSelectedPitchType('')}
              label="All"
              color="#86868B"
            />
            {summary.arsenal.map((a) => (
              <PitchPill
                key={a.pitch_type}
                active={selectedPitchType === a.pitch_type}
                onClick={() => setSelectedPitchType(a.pitch_type)}
                label={`${a.pitch_name || a.pitch_type} (${a.usage_pct}%)`}
                color={pitchColor(a.pitch_type)}
              />
            ))}
          </div>
        )}

        {/* ── OVERVIEW TAB — Savant-style percentile rankings + arsenal summary ── */}
        {tab === 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Percentile rankings panel (Savant-signature feature) */}
            <div style={cardStyle} className="p-5 lg:col-span-2">
              <div className="flex items-baseline justify-between mb-4">
                <h3 className="font-semibold tracking-tight" style={{ color: '#1D1D1F', fontSize: '1rem' }}>
                  Percentile Rankings
                </h3>
                <span className="text-xs" style={{ color: '#86868B' }}>
                  Among qualified MLB pitchers ({leaderboard.length})
                </span>
              </div>

              {percentiles && percentiles.length > 0 ? (
                <div className="space-y-2.5">
                  {percentiles.map((p) => (
                    <PercentileBar key={p.label} {...p} />
                  ))}
                </div>
              ) : (
                <div className="text-sm py-6 text-center" style={{ color: '#86868B' }}>
                  Not enough data to compute percentile rankings.
                </div>
              )}
            </div>

            {/* Quick arsenal stat block */}
            <div style={cardStyle} className="p-5">
              <h3 className="font-semibold tracking-tight mb-3" style={{ color: '#1D1D1F', fontSize: '1rem' }}>
                Arsenal
              </h3>
              <div className="space-y-2">
                {[...summary.arsenal].sort((a, b) => b.count - a.count).map((a) => (
                  <div key={a.pitch_type} className="flex items-center gap-2.5">
                    <div
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ backgroundColor: pitchColor(a.pitch_type), border: '1px solid rgba(0,0,0,0.12)' }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-sm font-medium truncate" style={{ color: '#1D1D1F' }}>
                          {a.pitch_name || a.pitch_type}
                        </span>
                        <span className="text-xs tabular-nums" style={{ color: '#86868B' }}>
                          {a.usage_pct}%
                        </span>
                      </div>
                      <div className="text-xs tabular-nums" style={{ color: '#86868B' }}>
                        {a.avg_velo?.toFixed(1) ?? '–'} mph
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── ARSENAL TAB ── */}
        {tab === 1 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Usage bar chart */}
            <div style={cardStyle} className="p-4">
              <h3 className="font-semibold tracking-tight mb-4" style={{ color: '#1D1D1F' }}>
                Pitch Usage
              </h3>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart
                  data={[...summary.arsenal].sort((a, b) => b.count - a.count)}
                  margin={{ left: 10, right: 10, bottom: 30 }}
                  layout="vertical"
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(0,0,0,0.06)" />
                  <XAxis type="number" tickFormatter={(v) => v + '%'} domain={[0, 'auto']}
                         tick={{ fontSize: 11, fill: '#86868B' }} axisLine={{ stroke: 'rgba(0,0,0,0.15)' }} />
                  <YAxis
                    type="category" dataKey="pitch_name" width={120}
                    tick={{ fontSize: 11, fill: '#1D1D1F' }} tickLine={false} axisLine={{ stroke: 'rgba(0,0,0,0.15)' }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#FFFFFF',
                      border: '1px solid rgba(0,0,0,0.10)',
                      color: '#1D1D1F',
                      fontSize: 12,
                      borderRadius: 8,
                    }}
                    formatter={(v) => v.toFixed(1) + '%'}
                  />
                  <Bar dataKey="usage_pct" isAnimationActive={false}>
                    {summary.arsenal.map((a) => (
                      <Cell key={a.pitch_type} fill={pitchColor(a.pitch_type)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Arsenal stats table */}
            <div style={cardStyle} className="overflow-hidden">
              <div className="px-4 py-3" style={{ borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
                <h3 className="font-semibold tracking-tight" style={{ color: '#1D1D1F' }}>
                  Arsenal Breakdown
                </h3>
              </div>
              <table className="savant-table">
                <thead>
                  <tr>
                    <th>Pitch</th>
                    <th>Usage</th>
                    <th>Velo</th>
                    <th>Spin</th>
                    <th>HB"</th>
                    <th>IVB"</th>
                    <th>Ext</th>
                  </tr>
                </thead>
                <tbody>
                  {[...summary.arsenal].sort((a, b) => b.count - a.count).map((a) => (
                    <tr key={a.pitch_type}>
                      <td>
                        <div className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded-full flex-shrink-0"
                            style={{ backgroundColor: pitchColor(a.pitch_type), border: '1px solid rgba(0,0,0,0.15)' }}
                          />
                          <span className="text-xs">{a.pitch_name || a.pitch_type}</span>
                        </div>
                      </td>
                      <td className="tabular-nums">{a.usage_pct}%</td>
                      <td className="tabular-nums">{a.avg_velo?.toFixed(1) ?? '–'}</td>
                      <td className="tabular-nums">{a.avg_spin ? Math.round(a.avg_spin) : '–'}</td>
                      <td className="tabular-nums">{a.avg_pfx_x != null ? (a.avg_pfx_x * 12).toFixed(1) : '–'}</td>
                      <td className="tabular-nums">{a.avg_pfx_z != null ? (a.avg_pfx_z * 12).toFixed(1) : '–'}</td>
                      <td className="tabular-nums">{a.avg_extension?.toFixed(1) ?? '–'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── LOCATION TAB ── */}
        {tab === 2 && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            <div>
              <div className="text-xs tracking-wider mb-2 uppercase font-semibold" style={{ color: '#86868B' }}>
                All Pitches ({filteredPitches.length})
              </div>
              <PitchLocationChart pitches={filteredPitches} height={320} title="" />
            </div>
            {summary.arsenal.filter((a) => !selectedPitchType || a.pitch_type === selectedPitchType)
              .map((a) => {
                const pts = pitches.filter((p) => p.pitch_type === a.pitch_type)
                return (
                  <div key={a.pitch_type}>
                    <div className="text-xs tracking-wider mb-2 uppercase font-semibold" style={{ color: '#86868B' }}>
                      {a.pitch_name || a.pitch_type} ({pts.length})
                    </div>
                    <PitchLocationChart pitches={pts} height={320} title="" />
                  </div>
                )
              })}
          </div>
        )}

        {/* ── MOVEMENT TAB ── */}
        {tab === 3 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <div className="text-xs tracking-wider mb-2 uppercase font-semibold" style={{ color: '#86868B' }}>
                All Pitches ({filteredPitches.length})
              </div>
              <PitchMovementChart pitches={filteredPitches} title="" />
            </div>
            <div style={cardStyle} className="p-3">
              <div className="text-xs tracking-wider mb-2 uppercase font-semibold" style={{ color: '#1D1D1F' }}>
                Velocity Trend (last 200 pitches)
              </div>
              <VeloTrendChart pitches={pitches.slice(0, 200).reverse()} arsenal={summary.arsenal} />
            </div>
          </div>
        )}

        {/* ── PITCH LOG TAB ── */}
        {tab === 4 && (
          <div style={cardStyle} className="overflow-hidden">
            <div
              className="px-4 py-3 flex items-center justify-between"
              style={{ borderBottom: '1px solid rgba(0,0,0,0.08)' }}
            >
              <h3 className="font-semibold tracking-tight" style={{ color: '#1D1D1F' }}>
                Pitch Log ({logTotal.toLocaleString()} total)
              </h3>
              <div className="flex gap-2 items-center text-xs" style={{ color: '#86868B' }}>
                <button
                  disabled={logOffset === 0}
                  onClick={() => setLogOffset(Math.max(0, logOffset - 200))}
                  className="px-3 py-1 rounded-full disabled:opacity-40 transition-colors"
                  style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.12)', color: '#1D1D1F' }}
                >← Prev</button>
                <span>Showing {logOffset + 1}–{Math.min(logOffset + 200, logTotal)}</span>
                <button
                  disabled={logOffset + 200 >= logTotal}
                  onClick={() => setLogOffset(logOffset + 200)}
                  className="px-3 py-1 rounded-full disabled:opacity-40 transition-colors"
                  style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.12)', color: '#1D1D1F' }}
                >Next →</button>
              </div>
            </div>
            <LeaderboardTable rows={pitches.slice(logOffset, logOffset + 200)} columns={PITCH_LOG_COLS} />
          </div>
        )}
      </div>
    </div>
  )
}

// ── Savant-style percentile bar ──────────────────────────────────────────────
function PercentileBar({ label, raw, pct, fmt }) {
  const pctNum = Math.round(pct * 100)
  const bubbleStyle = savantColor(pct, true)
  return (
    <div className="flex items-center gap-4">
      <div className="w-32 text-sm flex-shrink-0" style={{ color: '#1D1D1F' }}>{label}</div>
      <div className="flex-1 relative h-6 rounded-full" style={{ background: '#F5F5F7', border: '1px solid rgba(0,0,0,0.06)' }}>
        {/* Gradient fill */}
        <div
          className="absolute top-0 left-0 h-full rounded-full"
          style={{
            width: '100%',
            background: 'linear-gradient(to right, #2A63B6 0%, #8BB2D8 25%, #F5F5F7 50%, #ED887B 75%, #C42E3A 100%)',
            opacity: 0.45,
          }}
        />
        {/* Bubble marker */}
        <div
          className="absolute top-1/2 rounded-full text-[11px] font-semibold flex items-center justify-center"
          style={{
            left: `calc(${pctNum}% - 14px)`,
            transform: 'translateY(-50%)',
            width: 28, height: 28,
            ...bubbleStyle,
            border: '2px solid #FFFFFF',
            boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
          }}
        >
          {pctNum}
        </div>
      </div>
      <div className="w-24 text-right text-sm tabular-nums flex-shrink-0" style={{ color: '#1D1D1F' }}>
        {fmt ? fmt(raw) : raw}
      </div>
    </div>
  )
}

function PitchPill({ active, onClick, label, color }) {
  return (
    <button
      onClick={onClick}
      className="text-xs px-3 py-1 rounded-full transition-all duration-150 font-medium"
      style={
        active
          ? { backgroundColor: color, color: '#fff', border: `2px solid ${color}` }
          : {
              background: '#FFFFFF',
              color: '#86868B',
              border: '2px solid rgba(0,0,0,0.10)',
            }
      }
    >
      {label}
    </button>
  )
}

function VeloTrendChart({ pitches, arsenal }) {
  const data = pitches.map((p, i) => {
    const pt = p.pitch_type
    return { i, [pt]: p.release_speed }
  })

  const pitchTypes = arsenal.map((a) => a.pitch_type)

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ right: 10, left: -10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
        <XAxis dataKey="i" tick={{ fill: '#86868B', fontSize: 10 }} tickLine={false} axisLine={{ stroke: 'rgba(0,0,0,0.15)' }} />
        <YAxis domain={['auto', 'auto']} tick={{ fill: '#86868B', fontSize: 10 }} tickLine={false} axisLine={{ stroke: 'rgba(0,0,0,0.15)' }} />
        <Tooltip
          contentStyle={{
            background: '#FFFFFF',
            border: '1px solid rgba(0,0,0,0.10)',
            color: '#1D1D1F',
            fontSize: 11,
            borderRadius: 8,
          }}
          formatter={(v, name) => [v?.toFixed(1) + ' mph', PITCH_LABEL[name] || name]}
        />
        {pitchTypes.map((pt) => (
          <Line
            key={pt}
            type="monotone"
            dataKey={pt}
            stroke={pitchColor(pt)}
            dot={false}
            strokeWidth={1.5}
            connectNulls={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

import { useEffect } from 'react'
import { pitchColor, PITCH_LABEL } from '../../lib/pitchColors'

// ── Heat map (league-relative: p10/p90 per pitch type) ───────────────────────
function heatColor(val, p10, p90, higherIsBetter = true) {
  if (val == null || p10 == null || p90 == null || p10 === p90) return {}
  const pct = Math.max(0, Math.min(1, (val - p10) / (p90 - p10)))
  const adj = higherIsBetter ? pct : 1 - pct
  if (adj >= 0.85) return { backgroundColor: 'rgba(220,38,38,0.25)', color: '#FCA5A5', fontWeight: 600 }
  if (adj >= 0.65) return { backgroundColor: 'rgba(234,88,12,0.15)', color: '#FDB97D' }
  if (adj <= 0.15) return { backgroundColor: 'rgba(37,99,235,0.25)', color: '#93C5FD', fontWeight: 600 }
  if (adj <= 0.35) return { backgroundColor: 'rgba(14,165,233,0.12)', color: '#7DD3FC' }
  return {}
}

// Maps arsenal column keys → norm bucket keys returned by /pitch-type-norms
const NORM_KEY = {
  avg_velo:   'velo',
  avg_spin:   'spin',
  avg_ivb:    'ivb',
  zone_pct:   'zone_pct',
  chase_pct:  'chase_pct',
  whiff_pct:  'whiff_pct',
  avg_xwoba:  'xwoba',
}

// ── Strike zone SVG ──────────────────────────────────────────────────────────
const SZW = 240, SZH = 260, SZPAD = 18
const szScaleX = (x) => SZPAD + ((x + 1.5) / 3) * (SZW - SZPAD * 2)
const szScaleZ = (z) => SZH - SZPAD - ((z / 5.5) * (SZH - SZPAD * 2))
const SZ_L = szScaleX(-0.8308)
const SZ_R = szScaleX(0.8308)

function StrikeZonePlot({ pitches }) {
  const szTops = pitches.map((p) => p.sz_top).filter(Boolean)
  const szBots = pitches.map((p) => p.sz_bot).filter(Boolean)
  const med = (arr) => { const s = [...arr].sort((a, b) => a - b); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m-1] + s[m]) / 2 }
  const top = szTops.length ? med(szTops) : 3.4
  const bot = szBots.length ? med(szBots) : 1.6
  const szTop = szScaleZ(top), szBot = szScaleZ(bot)

  return (
    <div>
      <div className="text-xs text-mist tracking-wider mb-1 uppercase font-medium">Pitch Locations</div>
      <svg viewBox={`0 0 ${SZW} ${SZH}`} width="100%" style={{ maxHeight: 220 }}>
        {/* Outer box */}
        <rect x={SZPAD} y={SZPAD} width={SZW - SZPAD*2} height={SZH - SZPAD*2}
              fill="none" stroke="rgba(255,255,255,0.10)" strokeWidth="1" strokeDasharray="4,4" />
        {/* Strike zone */}
        <rect x={SZ_L} y={szTop} width={SZ_R - SZ_L} height={szBot - szTop}
              fill="none" stroke="rgba(255,255,255,0.30)" strokeWidth="1.5" />
        {/* Zone grid */}
        {[-0.277, 0.277].map((x) => (
          <line key={x} x1={szScaleX(x)} y1={szTop} x2={szScaleX(x)} y2={szBot}
                stroke="rgba(255,255,255,0.10)" strokeWidth="0.8" />
        ))}
        {[bot + (top - bot) / 3, bot + 2 * (top - bot) / 3].map((z) => (
          <line key={z} x1={SZ_L} y1={szScaleZ(z)} x2={SZ_R} y2={szScaleZ(z)}
                stroke="rgba(255,255,255,0.10)" strokeWidth="0.8" />
        ))}
        {/* Home plate */}
        <polygon
          points={`${szScaleX(-0.708)},${szScaleZ(0.2)} ${szScaleX(0.708)},${szScaleZ(0.2)} ${szScaleX(0.708)},${szScaleZ(0.05)} ${szScaleX(0)},${szScaleZ(-0.1)} ${szScaleX(-0.708)},${szScaleZ(0.05)}`}
          fill="rgba(255,255,255,0.25)" />
        {/* Pitches */}
        {pitches.map((p, i) => p.plate_x != null && p.plate_z != null && (
          <circle key={i} cx={szScaleX(p.plate_x)} cy={szScaleZ(p.plate_z)}
                  r={4.5} fill={pitchColor(p.pitch_type)} fillOpacity={0.85}
                  stroke="rgba(0,0,0,0.5)" strokeWidth={0.6} />
        ))}
      </svg>
    </div>
  )
}

// ── Release point SVG ────────────────────────────────────────────────────────
const RPW = 240, RPH = 200, RPAD = 18
// X: -4 to 4 ft  |  Z: 3 to 8 ft
const rpScaleX = (x) => RPAD + ((x + 4) / 8) * (RPW - RPAD * 2)
const rpScaleZ = (z) => RPH - RPAD - (((z - 3) / 5) * (RPH - RPAD * 2))

function ReleasePointPlot({ pitches }) {
  const valid = pitches.filter((p) => p.release_pos_x != null && p.release_pos_z != null)
  return (
    <div>
      <div className="text-xs text-mist tracking-wider mb-1 uppercase font-medium">Release Point</div>
      <svg viewBox={`0 0 ${RPW} ${RPH}`} width="100%" style={{ maxHeight: 200 }}>
        {/* Background */}
        <rect x={RPAD} y={RPAD} width={RPW - RPAD*2} height={RPH - RPAD*2}
              fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.10)" strokeWidth="1" />
        {/* Center line (rubber) */}
        <line x1={rpScaleX(0)} y1={RPAD} x2={rpScaleX(0)} y2={RPH - RPAD}
              stroke="rgba(255,255,255,0.15)" strokeWidth="1" strokeDasharray="3,3" />
        {/* Axis labels */}
        <text x={RPAD} y={RPH - 3} fontSize="8" fill="#86868B" fontFamily="monospace">L</text>
        <text x={RPW - RPAD - 4} y={RPH - 3} fontSize="8" fill="#86868B" fontFamily="monospace">R</text>
        <text x={2} y={RPAD + 6} fontSize="8" fill="#86868B" fontFamily="monospace">8ft</text>
        <text x={2} y={RPH - RPAD + 4} fontSize="8" fill="#86868B" fontFamily="monospace">3ft</text>
        {/* Pitches */}
        {valid.map((p, i) => (
          <circle key={i}
            cx={rpScaleX(p.release_pos_x)}
            cy={rpScaleZ(p.release_pos_z)}
            r={4.5}
            fill={pitchColor(p.pitch_type)}
            fillOpacity={0.85}
            stroke="rgba(0,0,0,0.5)"
            strokeWidth={0.6}
          />
        ))}
      </svg>
    </div>
  )
}

// ── Pitch breakdown table with heat map ──────────────────────────────────────
const ARSENAL_COLS = [
  { key: 'pitch_name', label: 'Pitch',   heat: false },
  { key: 'count',      label: 'Count',   heat: false },
  { key: 'usage_pct',  label: 'Pitch%',  heat: false,  fmt: (v) => v + '%' },
  { key: 'avg_velo',   label: 'Velo',    heat: true,   hib: true,  fmt: (v) => v?.toFixed(1) ?? '–' },
  { key: 'avg_spin',   label: 'Spin',    heat: true,   hib: true,  fmt: (v) => v ? Math.round(v) : '–' },
  { key: 'avg_hb',     label: 'HB',      heat: false,  fmt: (v) => v != null ? v.toFixed(1) + '"' : '–' },
  { key: 'avg_ivb',    label: 'IVB',     heat: true,   hib: true,  fmt: (v) => v != null ? v.toFixed(1) + '"' : '–' },
  { key: 'zone_pct',   label: 'Zone%',   heat: true,   hib: true,  fmt: (v) => v != null ? v + '%' : '–' },
  { key: 'chase_pct',  label: 'Chase%',  heat: true,   hib: true,  fmt: (v) => v != null ? v + '%' : '–' },
  { key: 'whiff_pct',  label: 'Whiff%',  heat: true,   hib: true,  fmt: (v) => v != null ? v + '%' : '–' },
  { key: 'avg_xwoba',  label: 'xwOBA',   heat: true,   hib: false, fmt: (v) => v?.toFixed(3) ?? '–' },
  // Stuff+ is already on a 100 = avg scale — use fixed bounds instead of league norms
  { key: 'stuff_plus', label: 'Stuff+',  heat: true,   hib: true,  fixedP10: 85, fixedP90: 120,
    fmt: (v) => v != null ? String(Math.round(v)) : '–' },
]

const LINE_COLS = [
  { key: 'pa',            label: 'PA' },
  { key: 'k',             label: 'K' },
  { key: 'bb',            label: 'BB' },
  { key: 'hits',          label: 'H' },
  { key: 'hr',            label: 'HR' },
  { key: 'hbp',           label: 'HBP' },
  { key: 'total_pitches', label: 'Pitches' },
  { key: 'whiffs',        label: 'Whiffs' },
  { key: 'strike_pct',    label: 'Strike%', fmt: (v) => v != null ? v + '%' : '–' },
]

// ── Main card ────────────────────────────────────────────────────────────────
export default function PitcherCard({ summary, norms = {}, onClose }) {
  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  if (!summary) return null

  const pitchTypes = [...new Set(summary.pitches.map((p) => p.pitch_type).filter(Boolean))]

  // Look up league p10/p90 for a given pitch type + column
  function getRange(pitchType, colKey) {
    const normKey = NORM_KEY[colKey]
    return normKey ? norms[pitchType]?.[normKey] : null
  }

  const photoUrl = `https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/${summary.pitcher_id}/headshot/67/current`

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.75)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="rounded-xl shadow-2xl w-full overflow-y-auto"
        style={{
          maxWidth: 860,
          maxHeight: '92vh',
          background: '#141414',
          border: '1px solid rgba(255,255,255,0.10)',
        }}
      >
        {/* Header */}
        <div
          className="px-5 py-4 flex items-center gap-4 rounded-t-xl sticky top-0 z-10"
          style={{
            background: '#1C1C1E',
            borderBottom: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <img
            src={photoUrl}
            alt={summary.pitcher_name}
            className="w-16 h-16 rounded-full object-cover flex-shrink-0"
            style={{ border: '2px solid rgba(14,165,233,0.40)', background: '#2C2C2E' }}
            onError={(e) => { e.target.style.display = 'none' }}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-3 flex-wrap">
              <h2 className="text-snow text-xl font-semibold tracking-tight leading-none">
                {summary.pitcher_name}
              </h2>
              <span className="text-mist text-sm">{summary.p_throws}HP</span>
              <span className="text-electric text-sm font-medium">{summary.game_date}</span>
              <span className="text-mist text-sm">
                {summary.away_team} @ {summary.home_team}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-mist hover:text-snow text-2xl font-light leading-none flex-shrink-0 ml-2 transition-colors"
          >
            ×
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Pitching line */}
          <div>
            <div className="text-xs text-mist uppercase tracking-wider mb-2 font-medium">Pitching Line</div>
            <div
              className="overflow-x-auto rounded-xl"
              style={{ border: '1px solid rgba(255,255,255,0.08)' }}
            >
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: '#1C1C1E', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                    {LINE_COLS.map((c) => (
                      <th key={c.key} className="px-3 py-2 text-center text-xs font-semibold text-mist uppercase tracking-wider whitespace-nowrap">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="text-center">
                    {LINE_COLS.map((c) => {
                      const val = summary.line[c.key]
                      return (
                        <td key={c.key} className="px-3 py-2 font-mono text-snow">
                          {c.fmt ? c.fmt(val) : (val ?? '–')}
                        </td>
                      )
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Scatter plots side by side */}
          <div className="grid grid-cols-2 gap-4">
            <div
              className="rounded-xl p-3"
              style={{ background: '#1C1C1E', border: '1px solid rgba(255,255,255,0.08)' }}
            >
              <StrikeZonePlot pitches={summary.pitches} />
            </div>
            <div
              className="rounded-xl p-3"
              style={{ background: '#1C1C1E', border: '1px solid rgba(255,255,255,0.08)' }}
            >
              <ReleasePointPlot pitches={summary.pitches} />
            </div>
          </div>

          {/* Pitch type legend */}
          <div className="flex flex-wrap gap-3">
            {pitchTypes.map((pt) => (
              <div key={pt} className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full flex-shrink-0"
                     style={{ backgroundColor: pitchColor(pt), border: '1px solid rgba(255,255,255,0.15)' }} />
                <span className="text-xs text-mist">{PITCH_LABEL[pt] || pt}</span>
              </div>
            ))}
          </div>

          {/* Pitch breakdown with heat map */}
          <div>
            <div className="text-xs text-mist uppercase tracking-wider mb-2 font-medium">Pitch Breakdown</div>
            <div
              className="overflow-x-auto rounded-xl"
              style={{ border: '1px solid rgba(255,255,255,0.08)' }}
            >
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: '#1C1C1E', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                    {ARSENAL_COLS.map((c) => (
                      <th key={c.key} className="px-3 py-2 text-center text-xs font-semibold text-mist uppercase tracking-wider whitespace-nowrap">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {summary.arsenal.map((row) => (
                    <tr
                      key={row.pitch_type}
                      style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}
                    >
                      {ARSENAL_COLS.map((c, ci) => {
                        const val = row[c.key]
                        const range = c.heat
                          ? (c.fixedP10 != null
                              ? { p10: c.fixedP10, p90: c.fixedP90 }
                              : getRange(row.pitch_type, c.key))
                          : null
                        const style = range
                          ? heatColor(val, range.p10, range.p90, c.hib !== false)
                          : {}
                        if (ci === 0) {
                          return (
                            <td key={c.key} className="px-3 py-2 whitespace-nowrap">
                              <span
                                className="inline-block px-2 py-0.5 rounded text-white text-xs font-bold"
                                style={{ backgroundColor: pitchColor(row.pitch_type) }}
                              >
                                {val}
                              </span>
                            </td>
                          )
                        }
                        return (
                          <td key={c.key} className="px-3 py-2 text-center font-mono text-snow" style={style}>
                            {c.fmt ? c.fmt(val) : (val ?? '–')}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

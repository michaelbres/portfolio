import { useEffect } from 'react'
import { pitchColor, PITCH_LABEL } from '../../lib/pitchColors'

// ── Heat map (league-relative: p10/p90 per pitch type) ───────────────────────
function heatColor(val, p10, p90, higherIsBetter = true) {
  if (val == null || p10 == null || p90 == null || p10 === p90) return {}
  const pct = Math.max(0, Math.min(1, (val - p10) / (p90 - p10)))
  const adj = higherIsBetter ? pct : 1 - pct
  if (adj >= 0.85) return { backgroundColor: '#fee2e2', color: '#7f1d1d', fontWeight: 600 }
  if (adj >= 0.65) return { backgroundColor: '#fff7ed', color: '#7c2d12' }
  if (adj <= 0.15) return { backgroundColor: '#dbeafe', color: '#1e3a5f', fontWeight: 600 }
  if (adj <= 0.35) return { backgroundColor: '#f0f9ff', color: '#0c4a6e' }
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
      <div className="text-xs font-bangers text-gray-500 tracking-wider mb-1 uppercase">Pitch Locations</div>
      <svg viewBox={`0 0 ${SZW} ${SZH}`} width="100%" style={{ maxHeight: 220 }}>
        {/* Outer box */}
        <rect x={SZPAD} y={SZPAD} width={SZW - SZPAD*2} height={SZH - SZPAD*2}
              fill="none" stroke="#ddd" strokeWidth="1" strokeDasharray="4,4" />
        {/* Strike zone */}
        <rect x={SZ_L} y={szTop} width={SZ_R - SZ_L} height={szBot - szTop}
              fill="none" stroke="#999" strokeWidth="1.5" />
        {/* Zone grid */}
        {[-0.277, 0.277].map((x) => (
          <line key={x} x1={szScaleX(x)} y1={szTop} x2={szScaleX(x)} y2={szBot}
                stroke="#ccc" strokeWidth="0.8" />
        ))}
        {[bot + (top - bot) / 3, bot + 2 * (top - bot) / 3].map((z) => (
          <line key={z} x1={SZ_L} y1={szScaleZ(z)} x2={SZ_R} y2={szScaleZ(z)}
                stroke="#ccc" strokeWidth="0.8" />
        ))}
        {/* Home plate */}
        <polygon
          points={`${szScaleX(-0.708)},${szScaleZ(0.2)} ${szScaleX(0.708)},${szScaleZ(0.2)} ${szScaleX(0.708)},${szScaleZ(0.05)} ${szScaleX(0)},${szScaleZ(-0.1)} ${szScaleX(-0.708)},${szScaleZ(0.05)}`}
          fill="#aaa" />
        {/* Pitches */}
        {pitches.map((p, i) => p.plate_x != null && p.plate_z != null && (
          <circle key={i} cx={szScaleX(p.plate_x)} cy={szScaleZ(p.plate_z)}
                  r={4.5} fill={pitchColor(p.pitch_type)} fillOpacity={0.8}
                  stroke="#000" strokeWidth={0.4} />
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
      <div className="text-xs font-bangers text-gray-500 tracking-wider mb-1 uppercase">Release Point</div>
      <svg viewBox={`0 0 ${RPW} ${RPH}`} width="100%" style={{ maxHeight: 200 }}>
        {/* Background */}
        <rect x={RPAD} y={RPAD} width={RPW - RPAD*2} height={RPH - RPAD*2}
              fill="#f8f9fa" stroke="#e5e7eb" strokeWidth="1" />
        {/* Center line (rubber) */}
        <line x1={rpScaleX(0)} y1={RPAD} x2={rpScaleX(0)} y2={RPH - RPAD}
              stroke="#d1d5db" strokeWidth="1" strokeDasharray="3,3" />
        {/* Axis labels */}
        <text x={RPAD} y={RPH - 3} fontSize="8" fill="#9ca3af" fontFamily="monospace">L</text>
        <text x={RPW - RPAD - 4} y={RPH - 3} fontSize="8" fill="#9ca3af" fontFamily="monospace">R</text>
        <text x={2} y={RPAD + 6} fontSize="8" fill="#9ca3af" fontFamily="monospace">8ft</text>
        <text x={2} y={RPH - RPAD + 4} fontSize="8" fill="#9ca3af" fontFamily="monospace">3ft</text>
        {/* Pitches */}
        {valid.map((p, i) => (
          <circle key={i}
            cx={rpScaleX(p.release_pos_x)}
            cy={rpScaleZ(p.release_pos_z)}
            r={4.5}
            fill={pitchColor(p.pitch_type)}
            fillOpacity={0.8}
            stroke="#000"
            strokeWidth={0.4}
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
      style={{ backgroundColor: 'rgba(0,0,0,0.65)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="bg-white rounded-xl shadow-2xl w-full overflow-y-auto"
        style={{ maxWidth: 860, maxHeight: '92vh' }}
      >
        {/* Header */}
        <div className="bg-sv-dark px-5 py-4 flex items-center gap-4 rounded-t-xl sticky top-0 z-10">
          <img
            src={photoUrl}
            alt={summary.pitcher_name}
            className="w-16 h-16 rounded-full object-cover border-2 border-sv-red bg-gray-700 flex-shrink-0"
            onError={(e) => { e.target.style.display = 'none' }}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-3 flex-wrap">
              <h2 className="font-bangers text-white text-2xl tracking-wider leading-none">
                {summary.pitcher_name}
              </h2>
              <span className="text-gray-400 text-sm font-sans">{summary.p_throws}HP</span>
              <span className="text-sv-red font-bangers tracking-wider">{summary.game_date}</span>
              <span className="text-gray-300 text-sm font-sans">
                {summary.away_team} @ {summary.home_team}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl font-light leading-none flex-shrink-0 ml-2"
          >
            ×
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Pitching line */}
          <div>
            <div className="text-xs font-bangers tracking-wider text-gray-400 uppercase mb-1">Pitching Line</div>
            <div className="overflow-x-auto border border-gray-200 rounded">
              <table className="w-full text-sm font-sans">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    {LINE_COLS.map((c) => (
                      <th key={c.key} className="px-3 py-1.5 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
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
                        <td key={c.key} className="px-3 py-2 font-mono text-gray-800">
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
            <div className="border border-gray-200 rounded p-3 bg-gray-50">
              <StrikeZonePlot pitches={summary.pitches} />
            </div>
            <div className="border border-gray-200 rounded p-3 bg-gray-50">
              <ReleasePointPlot pitches={summary.pitches} />
            </div>
          </div>

          {/* Pitch type legend */}
          <div className="flex flex-wrap gap-3">
            {pitchTypes.map((pt) => (
              <div key={pt} className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full border border-black/10 flex-shrink-0"
                     style={{ backgroundColor: pitchColor(pt) }} />
                <span className="text-xs text-gray-500 font-sans">{PITCH_LABEL[pt] || pt}</span>
              </div>
            ))}
          </div>

          {/* Pitch breakdown with heat map */}
          <div>
            <div className="text-xs font-bangers tracking-wider text-gray-400 uppercase mb-1">Pitch Breakdown</div>
            <div className="overflow-x-auto border border-gray-200 rounded">
              <table className="w-full text-sm font-sans">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    {ARSENAL_COLS.map((c) => (
                      <th key={c.key} className="px-3 py-1.5 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {summary.arsenal.map((row) => (
                    <tr key={row.pitch_type} className="border-b border-gray-100">
                      {ARSENAL_COLS.map((c, ci) => {
                        const val = row[c.key]
                        const range = c.heat ? getRange(row.pitch_type, c.key) : null
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
                          <td key={c.key} className="px-3 py-2 text-center font-mono" style={style}>
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

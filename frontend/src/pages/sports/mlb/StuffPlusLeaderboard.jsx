import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../../../components/Navbar'
import LeaderboardTable from '../../../components/mlb/LeaderboardTable'
import { fairValue } from '../../../lib/api'

// ── Helpers ───────────────────────────────────────────────────────────────────

// Stuff+ color: 100 = league average, higher = better
function stuffColor(val) {
  if (val == null) return 'text-mist'
  if (val >= 120) return 'text-red-300'
  if (val >= 110) return 'text-orange-300'
  if (val >= 100) return 'text-snow'
  if (val >= 90)  return 'text-sky-300'
  return 'text-blue-400'
}

// Pitch type badge colors
const PT_COLORS = {
  FF: 'bg-red-900/30 text-red-300 border-red-800/40',
  SI: 'bg-orange-900/30 text-orange-300 border-orange-800/40',
  FC: 'bg-yellow-900/30 text-yellow-300 border-yellow-800/40',
  SL: 'bg-blue-900/30 text-blue-300 border-blue-800/40',
  ST: 'bg-indigo-900/30 text-indigo-300 border-indigo-800/40',
  SV: 'bg-indigo-900/30 text-indigo-300 border-indigo-800/40',
  CU: 'bg-purple-900/30 text-purple-300 border-purple-800/40',
  KC: 'bg-violet-900/30 text-violet-300 border-violet-800/40',
  CH: 'bg-emerald-900/30 text-emerald-300 border-emerald-800/40',
  FS: 'bg-teal-900/30 text-teal-300 border-teal-800/40',
}
function ptColor(pt) {
  return PT_COLORS[pt] || 'bg-smoke/30 text-mist border-smoke/40'
}

const PITCH_TYPE_NAMES = {
  FF: '4-Seam', SI: 'Sinker', FC: 'Cutter', SL: 'Slider', ST: 'Sweeper',
  SV: 'Slurve',  CU: 'Curveball', KC: 'Knuckle Curve', CH: 'Changeup', FS: 'Splitter',
}

const MIN_PITCHES_OPTIONS = [25, 50, 100, 200]

// ── Pitch-type tab columns ────────────────────────────────────────────────────
const PT_COLS = [
  {
    key: 'pitcher_name',
    label: 'Pitcher',
    description: 'Pitcher name',
  },
  {
    key: 'stuff_plus',
    label: 'Stuff+',
    description: '100 = league average for this pitch type. Higher = more whiff-inducing.',
    colorScale: true,
    higherIsBetter: true,
    format: (v) => v?.toFixed(0),
  },
  {
    key: 'n_pitches',
    label: 'Pitches',
    description: 'Total pitches thrown this season',
    format: (v) => v?.toLocaleString(),
  },
]

// ── Main component ────────────────────────────────────────────────────────────

export default function StuffPlusLeaderboard() {
  const currentYear = new Date().getFullYear()
  const [season, setSeason]         = useState(currentYear)
  const [minPitches, setMinPitches] = useState(50)
  const [activeTab, setActiveTab]   = useState('overall')
  const [data, setData]             = useState(null)
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState(null)

  const fetchData = useCallback(async (s, mp) => {
    setLoading(true)
    setError(null)
    try {
      const { data: d } = await fairValue.stuffPlusLeaderboard({ season: s, min_pitches: mp })
      setData(d)
    } catch {
      setError('Failed to load Stuff+ data. Run POST /api/fair-value/admin/stuff-plus to train the model first.')
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData(season, minPitches)
  }, [season, minPitches, fetchData])

  // If current tab disappeared after a filter change, reset to overall
  useEffect(() => {
    if (activeTab !== 'overall' && data && !data.pitch_types_available?.includes(activeTab)) {
      setActiveTab('overall')
    }
  }, [data, activeTab])

  const pitchTypes = data?.pitch_types_available ?? []
  const overall    = data?.overall ?? []
  const byPt       = data?.by_pitch_type ?? {}

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#080808' }}>
      <Navbar />

      <div className="max-w-7xl mx-auto px-6 py-10">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <span
              className="text-xs font-semibold px-2 py-0.5 rounded"
              style={{ backgroundColor: 'rgba(168,85,247,0.15)', color: '#A855F7' }}
            >
              MLB
            </span>
            <span className="text-mist text-xs">Pitch Quality</span>
          </div>
          <h1
            className="text-2xl font-semibold text-snow tracking-tight"
            style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", Inter, sans-serif' }}
          >
            Stuff+ Leaderboard
          </h1>
          <p className="text-mist text-sm mt-1 max-w-2xl">
            Gradient-boosted whiff probability model scaled to 100&nbsp;=&nbsp;league average per pitch type.
            Overall Stuff+ is a pitch-count-weighted average across all pitch types.
          </p>
        </div>

        {/* ── Controls ───────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-4 mb-6">
          {/* Season selector */}
          <div className="flex items-center gap-2">
            <span className="text-mist text-sm">Season</span>
            <select
              value={season}
              onChange={(e) => setSeason(Number(e.target.value))}
              className="text-sm rounded-lg px-3 py-1.5 text-snow"
              style={{
                backgroundColor: '#1C1C1E',
                border: '1px solid rgba(255,255,255,0.08)',
                outline: 'none',
              }}
            >
              {[currentYear, currentYear - 1, currentYear - 2].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          {/* Min pitches filter */}
          <div className="flex items-center gap-2">
            <span className="text-mist text-sm">Min pitches</span>
            <div
              className="flex rounded-lg overflow-hidden"
              style={{ border: '1px solid rgba(255,255,255,0.08)' }}
            >
              {MIN_PITCHES_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  onClick={() => setMinPitches(opt)}
                  className="px-3 py-1.5 text-sm transition-colors"
                  style={{
                    backgroundColor: minPitches === opt ? 'rgba(168,85,247,0.20)' : '#1C1C1E',
                    color:           minPitches === opt ? '#A855F7' : '#86868B',
                    fontWeight:      minPitches === opt ? 500 : 400,
                  }}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>

          {loading && (
            <span className="text-mist text-sm animate-pulse">Loading…</span>
          )}
        </div>

        {/* ── Error ──────────────────────────────────────────────────────── */}
        {error && (
          <div
            className="mb-6 px-4 py-3 rounded-xl text-sm"
            style={{
              backgroundColor: 'rgba(239,68,68,0.10)',
              color: '#FCA5A5',
              border: '1px solid rgba(239,68,68,0.20)',
            }}
          >
            {error}
          </div>
        )}

        {/* ── Tab bar ────────────────────────────────────────────────────── */}
        <div
          className="flex flex-wrap gap-1 mb-4 p-1 rounded-xl w-fit"
          style={{ backgroundColor: '#1C1C1E', border: '1px solid rgba(255,255,255,0.06)' }}
        >
          <TabBtn active={activeTab === 'overall'} onClick={() => setActiveTab('overall')}>
            Overall
          </TabBtn>
          {pitchTypes.map((pt) => (
            <TabBtn key={pt} active={activeTab === pt} onClick={() => setActiveTab(pt)}>
              <span className={`px-1.5 py-0.5 rounded text-xs font-mono border ${ptColor(pt)}`}>
                {pt}
              </span>
              {PITCH_TYPE_NAMES[pt] && (
                <span className="ml-1 text-xs hidden sm:inline">
                  {PITCH_TYPE_NAMES[pt]}
                </span>
              )}
            </TabBtn>
          ))}
        </div>

        {/* ── Table ──────────────────────────────────────────────────────── */}
        <div className="bento-tile overflow-hidden">
          {activeTab === 'overall'
            ? <OverallTable rows={overall} />
            : (
              <LeaderboardTable
                rows={byPt[activeTab] ?? []}
                columns={PT_COLS}
                defaultSort="stuff_plus"
                linkTo
              />
            )
          }
        </div>

        {/* ── Footer meta ────────────────────────────────────────────────── */}
        {data && !loading && (
          <p className="text-mist text-xs mt-4 text-right">
            {overall.length} pitchers · {season} season · min {minPitches} pitches per pitch type
          </p>
        )}
      </div>
    </div>
  )
}

// ── Tab button ────────────────────────────────────────────────────────────────

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm transition-colors"
      style={{
        backgroundColor: active ? 'rgba(168,85,247,0.20)' : 'transparent',
        color:           active ? '#A855F7' : '#86868B',
        fontWeight:      active ? 500 : 400,
      }}
    >
      {children}
    </button>
  )
}

// ── Overall tab table ─────────────────────────────────────────────────────────

function OverallTable({ rows }) {
  const [sortKey, setSortKey] = useState('overall_stuff_plus')
  const [sortDir, setSortDir] = useState('desc')

  const handleSort = (key) => {
    if (sortKey === key) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else { setSortKey(key); setSortDir('desc') }
  }

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey]
    if (av == null) return 1
    if (bv == null) return -1
    return sortDir === 'desc' ? bv - av : av - bv
  })

  const COLS = [
    {
      key:   'overall_stuff_plus',
      label: 'Stuff+',
      title: 'Pitch-count-weighted average Stuff+ across all pitch types',
    },
    {
      key:   'n_pitches_total',
      label: 'Pitches',
      title: 'Total pitches thrown this season',
    },
    {
      key:   'n_pitch_types',
      label: 'Types',
      title: 'Number of distinct pitch types scored',
    },
  ]

  if (rows.length === 0) {
    return (
      <div className="text-center py-16 text-mist text-sm">
        No Stuff+ data yet.{' '}
        <span className="text-snow">
          Hit <code className="bg-smoke/40 px-1.5 py-0.5 rounded text-xs font-mono">
            POST /api/fair-value/admin/stuff-plus
          </code> to train the model on this season's Statcast data.
        </span>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="savant-table">
        <thead>
          <tr>
            <th className="w-8 text-center">#</th>
            <th>Pitcher</th>
            {COLS.map((c) => (
              <th
                key={c.key}
                onClick={() => handleSort(c.key)}
                title={c.title}
                style={
                  sortKey === c.key
                    ? { background: 'rgba(168,85,247,0.18)', color: '#A855F7' }
                    : {}
                }
              >
                <span className="flex items-center gap-1">
                  {c.label}
                  {sortKey === c.key && (
                    <span className="opacity-70 text-xs">
                      {sortDir === 'desc' ? '▼' : '▲'}
                    </span>
                  )}
                </span>
              </th>
            ))}
            <th style={{ minWidth: 220 }}>By Pitch Type</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={row.pitcher_id}>
              <td className="text-center text-mist text-xs">{i + 1}</td>

              {/* Pitcher name — linked to pitcher detail */}
              <td>
                <Link
                  to={`/sports/mlb/pitcher/${row.pitcher_id}`}
                  className="text-electric hover:underline font-medium"
                >
                  {row.pitcher_name ?? '–'}
                </Link>
              </td>

              {/* Overall Stuff+ */}
              <td>
                <span className={`text-lg font-semibold tabular-nums ${stuffColor(row.overall_stuff_plus)}`}>
                  {row.overall_stuff_plus?.toFixed(0) ?? '–'}
                </span>
              </td>

              {/* Total pitches */}
              <td className="text-mist tabular-nums">
                {row.n_pitches_total?.toLocaleString() ?? '–'}
              </td>

              {/* # pitch types */}
              <td className="text-mist tabular-nums">
                {row.n_pitch_types ?? '–'}
              </td>

              {/* Pitch breakdown pills */}
              <td>
                <div className="flex flex-wrap gap-1.5">
                  {(row.pitch_breakdown ?? []).map((pb) => (
                    <span
                      key={pb.pitch_type}
                      title={`${pb.pitch_type} — ${pb.n_pitches?.toLocaleString()} pitches`}
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-mono ${ptColor(pb.pitch_type)}`}
                    >
                      <span className="opacity-60">{pb.pitch_type}</span>
                      <span className={`font-bold ${stuffColor(pb.stuff_plus)}`}>
                        {pb.stuff_plus?.toFixed(0) ?? '–'}
                      </span>
                    </span>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

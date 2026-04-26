import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../../../components/Navbar'
import PageHeader from '../../../components/PageHeader'
import LeaderboardTable from '../../../components/mlb/LeaderboardTable'
import { fairValue } from '../../../lib/api'
import { savantColor, stuffPlusPct } from '../../../lib/savantColor'

// Pitch type badge colors — light palette
const PT_COLORS = {
  FF: { bg: '#FEE4E2', fg: '#B42318', border: '#FECDCA' },
  SI: { bg: '#FEF0C7', fg: '#93370D', border: '#FEDF89' },
  FC: { bg: '#FEF7C3', fg: '#854708', border: '#FEEE95' },
  SL: { bg: '#DBEAFE', fg: '#1849A9', border: '#B2CCFF' },
  ST: { bg: '#E0E7FF', fg: '#3538CD', border: '#C7D7FE' },
  SV: { bg: '#E0E7FF', fg: '#3538CD', border: '#C7D7FE' },
  CU: { bg: '#EDE9FE', fg: '#5925DC', border: '#D9D6FE' },
  KC: { bg: '#F4EBFF', fg: '#6941C6', border: '#E9D7FE' },
  CH: { bg: '#D1FADF', fg: '#027A48', border: '#A6F4C5' },
  FS: { bg: '#CCFBEF', fg: '#107569', border: '#99F6E0' },
}
function ptStyle(pt) {
  const c = PT_COLORS[pt] || { bg: '#F2F4F7', fg: '#344054', border: '#D0D5DD' }
  return {
    background: c.bg,
    color: c.fg,
    border: `1px solid ${c.border}`,
  }
}

const PITCH_TYPE_NAMES = {
  FF: '4-Seam', SI: 'Sinker', FC: 'Cutter', SL: 'Slider', ST: 'Sweeper',
  SV: 'Slurve',  CU: 'Curveball', KC: 'Knuckle Curve', CH: 'Changeup', FS: 'Splitter',
}

const MIN_PITCHES_OPTIONS = [25, 50, 100, 200]

// ── Pitch-type tab columns ────────────────────────────────────────────────────
const PT_COLS = [
  { key: 'pitcher_name', label: 'Pitcher', description: 'Pitcher name' },
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

  useEffect(() => { fetchData(season, minPitches) }, [season, minPitches, fetchData])

  useEffect(() => {
    if (activeTab !== 'overall' && data && !data.pitch_types_available?.includes(activeTab)) {
      setActiveTab('overall')
    }
  }, [data, activeTab])

  const pitchTypes = data?.pitch_types_available ?? []
  const overall    = data?.overall ?? []
  const byPt       = data?.by_pitch_type ?? {}

  return (
    <div className="min-h-screen" style={{ background: '#F5F5F7' }}>
      <Navbar />

      <PageHeader
        kicker="MLB · Pitch Quality"
        kickerColor="#6941C6"
        kickerBg="rgba(105,65,198,0.10)"
        title="Stuff+ Leaderboard"
        subtitle="Gradient-boosted whiff probability model scaled to 100 = league average per pitch type. Overall Stuff+ is a pitch-count-weighted average across all pitch types."
      />

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* ── Controls ───────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-4 mb-6">
          <div className="flex items-center gap-2">
            <span className="text-sm" style={{ color: '#86868B' }}>Season</span>
            <select
              value={season}
              onChange={(e) => setSeason(Number(e.target.value))}
              className="text-sm rounded-lg px-3 py-1.5"
              style={{
                background: '#FFFFFF',
                border: '1px solid rgba(0,0,0,0.12)',
                color: '#1D1D1F',
                outline: 'none',
              }}
            >
              {[currentYear, currentYear - 1, currentYear - 2].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm" style={{ color: '#86868B' }}>Min pitches</span>
            <div
              className="flex rounded-full overflow-hidden p-1"
              style={{ background: '#E8E8ED' }}
            >
              {MIN_PITCHES_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  onClick={() => setMinPitches(opt)}
                  className="px-3 py-1 text-sm rounded-full transition-colors"
                  style={{
                    background: minPitches === opt ? '#FFFFFF' : 'transparent',
                    color:      minPitches === opt ? '#1D1D1F' : '#86868B',
                    fontWeight: minPitches === opt ? 500 : 400,
                    boxShadow:  minPitches === opt ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
                  }}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>

          {loading && <span className="text-sm animate-pulse" style={{ color: '#86868B' }}>Loading…</span>}
        </div>

        {error && (
          <div
            className="mb-6 px-4 py-3 rounded-xl text-sm"
            style={{
              background: 'rgba(239,68,68,0.08)',
              color: '#B42318',
              border: '1px solid rgba(239,68,68,0.25)',
            }}
          >
            {error}
          </div>
        )}

        {/* ── Tab bar — Apple segmented control style ────────────────────── */}
        <div
          className="flex flex-wrap gap-1 mb-4 p-1 rounded-full w-fit"
          style={{ background: '#E8E8ED' }}
        >
          <TabBtn active={activeTab === 'overall'} onClick={() => setActiveTab('overall')}>
            Overall
          </TabBtn>
          {pitchTypes.map((pt) => (
            <TabBtn key={pt} active={activeTab === pt} onClick={() => setActiveTab(pt)}>
              <span
                className="px-1.5 py-0.5 rounded text-xs font-mono"
                style={ptStyle(pt)}
              >
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
        <div
          className="rounded-xl overflow-hidden"
          style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.08)' }}
        >
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

        {data && !loading && (
          <p className="text-xs mt-4 text-right" style={{ color: '#86868B' }}>
            {overall.length} pitchers · {season} season · min {minPitches} pitches per pitch type
          </p>
        )}
      </div>
    </div>
  )
}

// ── Segmented tab button ──────────────────────────────────────────────────────

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1 px-3 py-1 rounded-full text-sm transition-colors"
      style={{
        background: active ? '#FFFFFF' : 'transparent',
        color:      active ? '#1D1D1F' : '#86868B',
        fontWeight: active ? 500 : 400,
        boxShadow:  active ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
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
    { key: 'overall_stuff_plus', label: 'Stuff+', title: 'Pitch-count-weighted average Stuff+ across all pitch types' },
    { key: 'n_pitches_total',    label: 'Pitches', title: 'Total pitches thrown this season' },
    { key: 'n_pitch_types',      label: 'Types',   title: 'Number of distinct pitch types scored' },
  ]

  if (rows.length === 0) {
    return (
      <div className="text-center py-16 text-sm" style={{ color: '#86868B' }}>
        No Stuff+ data yet.{' '}
        <span style={{ color: '#1D1D1F' }}>
          Hit <code className="px-1.5 py-0.5 rounded text-xs font-mono" style={{ background: '#F2F4F7' }}>
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
                    ? { background: 'rgba(0,102,204,0.10)', color: '#0066CC' }
                    : undefined
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
          {sorted.map((row, i) => {
            const overallStyle = savantColor(stuffPlusPct(row.overall_stuff_plus), true)
            return (
              <tr key={row.pitcher_id}>
                <td className="text-center text-xs" style={{ color: '#86868B' }}>{i + 1}</td>

                <td>
                  <Link
                    to={`/sports/mlb/pitcher/${row.pitcher_id}`}
                    className="font-medium hover:underline"
                    style={{ color: '#0066CC' }}
                  >
                    {row.pitcher_name ?? '–'}
                  </Link>
                </td>

                <td style={overallStyle} className="tabular-nums font-semibold">
                  {row.overall_stuff_plus?.toFixed(0) ?? '–'}
                </td>

                <td className="tabular-nums" style={{ color: '#86868B' }}>
                  {row.n_pitches_total?.toLocaleString() ?? '–'}
                </td>

                <td className="tabular-nums" style={{ color: '#86868B' }}>
                  {row.n_pitch_types ?? '–'}
                </td>

                <td>
                  <div className="flex flex-wrap gap-1.5">
                    {(row.pitch_breakdown ?? []).map((pb) => {
                      const sp = pb.stuff_plus
                      const cellStyle = savantColor(stuffPlusPct(sp), true)
                      return (
                        <span
                          key={pb.pitch_type}
                          title={`${pb.pitch_type} — ${pb.n_pitches?.toLocaleString()} pitches`}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-mono"
                          style={{
                            border: '1px solid rgba(0,0,0,0.08)',
                            ...cellStyle,
                          }}
                        >
                          <span style={{ opacity: 0.7 }}>{pb.pitch_type}</span>
                          <span className="font-bold">
                            {sp?.toFixed(0) ?? '–'}
                          </span>
                        </span>
                      )
                    })}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

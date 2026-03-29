import { useState, useEffect, useRef } from 'react'
import { mlb } from '../../lib/api'
import { pitchColor } from '../../lib/pitchColors'

const LINE_COLS = [
  { key: 'pa',            label: 'PA',      title: 'Batters faced' },
  { key: 'k',             label: 'K',       title: 'Strikeouts' },
  { key: 'bb',            label: 'BB',      title: 'Walks' },
  { key: 'hits',          label: 'H',       title: 'Hits allowed' },
  { key: 'hr',            label: 'HR',      title: 'Home runs' },
  { key: 'hbp',           label: 'HBP',     title: 'Hit by pitch' },
  { key: 'total_pitches', label: 'Pitches', title: 'Total pitches' },
  { key: 'whiffs',        label: 'Whiffs',  title: 'Swinging strikes' },
  { key: 'strike_pct',    label: 'Strike%', title: 'Strike percentage', fmt: (v) => v != null ? v + '%' : '–' },
]

const ARSENAL_COLS = [
  { key: 'pitch_name', label: 'Pitch',  fmt: null },
  { key: 'count',      label: 'Count',  fmt: null },
  { key: 'usage_pct',  label: 'Pitch%', fmt: (v) => v + '%' },
  { key: 'avg_velo',   label: 'Velo',   fmt: (v) => v?.toFixed(1) ?? '–' },
  { key: 'avg_spin',   label: 'Spin',   fmt: (v) => v ? Math.round(v) : '–' },
  { key: 'avg_hb',     label: 'HB',     fmt: (v) => v != null ? v.toFixed(1) + '"' : '–' },
  { key: 'avg_ivb',    label: 'IVB',    fmt: (v) => v != null ? v.toFixed(1) + '"' : '–' },
  { key: 'zone_pct',   label: 'Zone%',  fmt: (v) => v != null ? v + '%' : '–' },
  { key: 'chase_pct',  label: 'Chase%', fmt: (v) => v != null ? v + '%' : '–' },
  { key: 'whiff_pct',  label: 'Whiff%', fmt: (v) => v != null ? v + '%' : '–' },
  { key: 'avg_xwoba',  label: 'xwOBA',  fmt: (v) => v?.toFixed(3) ?? '–' },
]

function formatDateLabel(dateStr) {
  // "2026-03-28" → "Mar 28"
  const [y, m, d] = dateStr.split('-')
  const dt = new Date(Number(y), Number(m) - 1, Number(d))
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function groupByGame(pitchers) {
  const map = new Map()
  for (const p of pitchers) {
    const key = p.game_pk
    if (!map.has(key)) map.set(key, { home: p.home_team, away: p.away_team, pitchers: [] })
    map.get(key).pitchers.push(p)
  }
  return [...map.values()].sort((a, b) =>
    `${a.away}${a.home}`.localeCompare(`${b.away}${b.home}`)
  )
}

export default function GameSummary({ season }) {
  const [dates, setDates]               = useState([])
  const [selectedDate, setSelectedDate] = useState(null)
  const [gamePitchers, setGamePitchers] = useState([])   // pitchers for selected date
  const [summary, setSummary]           = useState(null)
  const [selectedKey, setSelectedKey]   = useState(null) // "pitcher_id:game_pk"
  const [loadingDates, setLoadingDates] = useState(false)
  const [loadingPitchers, setLoadingPitchers] = useState(false)
  const [loadingSummary, setLoadingSummary]   = useState(false)
  const dateStripRef = useRef(null)

  // Load available dates whenever season changes
  useEffect(() => {
    setLoadingDates(true)
    setSelectedDate(null)
    setGamePitchers([])
    setSummary(null)
    mlb.gameDates({ season })
      .then((res) => { setDates(res.data); if (res.data.length) selectDate(res.data[0]) })
      .catch(() => {})
      .finally(() => setLoadingDates(false))
  }, [season])

  async function selectDate(dateStr) {
    setSelectedDate(dateStr)
    setSummary(null)
    setSelectedKey(null)
    setGamePitchers([])
    setLoadingPitchers(true)
    try {
      const res = await mlb.pitchersByDate({ game_date: dateStr })
      setGamePitchers(res.data)
    } catch { /* ignore */ } finally {
      setLoadingPitchers(false)
    }
  }

  async function selectPitcher(pitcher) {
    const key = `${pitcher.pitcher_id}:${pitcher.game_pk}`
    if (key === selectedKey) return
    setSelectedKey(key)
    setSummary(null)
    setLoadingSummary(true)
    try {
      const res = await mlb.pitcherGameSummary(pitcher.pitcher_id, pitcher.game_pk)
      setSummary(res.data)
    } catch { /* ignore */ } finally {
      setLoadingSummary(false)
    }
  }

  const games = groupByGame(gamePitchers)

  return (
    <div className="space-y-4">
      {/* Date strip */}
      <div className="bg-white border border-gray-200 rounded p-3">
        <p className="text-xs font-sans text-gray-400 uppercase tracking-wider mb-2">Select Date</p>
        {loadingDates ? (
          <p className="text-sm text-gray-400 font-sans animate-pulse">Loading dates…</p>
        ) : dates.length === 0 ? (
          <p className="text-sm text-gray-400 font-sans">No game data available for this season.</p>
        ) : (
          <div
            ref={dateStripRef}
            className="flex gap-2 overflow-x-auto pb-1"
            style={{ scrollbarWidth: 'thin' }}
          >
            {dates.map((d) => (
              <button
                key={d}
                onClick={() => selectDate(d)}
                className={`flex-shrink-0 px-3 py-1.5 rounded text-xs font-bangers tracking-wider transition-colors whitespace-nowrap ${
                  d === selectedDate
                    ? 'bg-sv-red text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {formatDateLabel(d)}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Pitchers for selected date */}
      {selectedDate && (
        <div className="bg-white border border-gray-200 rounded p-4">
          <p className="text-xs font-sans text-gray-400 uppercase tracking-wider mb-3">
            Pitchers — {formatDateLabel(selectedDate)}
          </p>
          {loadingPitchers ? (
            <p className="text-sm text-gray-400 font-sans animate-pulse">Loading pitchers…</p>
          ) : games.length === 0 ? (
            <p className="text-sm text-gray-400 font-sans">No pitching data for this date.</p>
          ) : (
            <div className="space-y-4">
              {games.map((game) => (
                <div key={game.home + game.away}>
                  <div className="text-xs font-bangers tracking-wider text-sv-blue mb-1.5">
                    {game.away} @ {game.home}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {game.pitchers.map((p) => {
                      const key = `${p.pitcher_id}:${p.game_pk}`
                      const active = key === selectedKey
                      return (
                        <button
                          key={key}
                          onClick={() => selectPitcher(p)}
                          className={`px-3 py-1.5 rounded border text-xs font-sans transition-colors ${
                            active
                              ? 'bg-sv-dark text-white border-sv-dark'
                              : 'bg-white text-gray-700 border-gray-300 hover:border-sv-blue hover:text-sv-blue'
                          }`}
                        >
                          {p.pitcher_name}
                          <span className={`ml-1.5 ${active ? 'text-gray-400' : 'text-gray-400'}`}>
                            {p.total_pitches}p
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Game summary */}
      {loadingSummary && (
        <p className="text-sm text-gray-400 font-sans animate-pulse px-1">Loading summary…</p>
      )}

      {summary && (
        <div className="space-y-4">
          {/* Header */}
          <div className="bg-sv-dark rounded px-5 py-4 flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <h2 className="font-bangers text-white text-2xl tracking-wider">{summary.pitcher_name}</h2>
            <span className="text-gray-400 text-sm font-sans">{summary.p_throws}HP</span>
            <span className="text-sv-red font-bangers tracking-wider text-lg">{summary.game_date}</span>
            <span className="text-gray-300 text-sm font-sans">
              {summary.away_team} @ {summary.home_team}
            </span>
          </div>

          {/* Pitching line */}
          <div className="bg-white border border-gray-200 rounded overflow-hidden">
            <div className="bg-sv-blue px-4 py-2">
              <span className="font-bangers text-white tracking-wider text-sm">PITCHING LINE</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm font-sans">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    {LINE_COLS.map((c) => (
                      <th key={c.key} title={c.title} className="px-4 py-2 text-center font-semibold text-gray-600 text-xs uppercase tracking-wider whitespace-nowrap">
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
                        <td key={c.key} className="px-4 py-3 font-mono text-gray-800 border-b border-gray-100">
                          {c.fmt ? c.fmt(val) : (val ?? '–')}
                        </td>
                      )
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Pitch breakdown */}
          <div className="bg-white border border-gray-200 rounded overflow-hidden">
            <div className="bg-sv-blue px-4 py-2">
              <span className="font-bangers text-white tracking-wider text-sm">PITCH BREAKDOWN</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm font-sans">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    {ARSENAL_COLS.map((c) => (
                      <th key={c.key} className="px-3 py-2 text-center font-semibold text-gray-600 text-xs uppercase tracking-wider whitespace-nowrap">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {summary.arsenal.map((row) => (
                    <tr key={row.pitch_type} className="border-b border-gray-100 hover:bg-gray-50">
                      {ARSENAL_COLS.map((c, ci) => {
                        const val = row[c.key]
                        if (ci === 0) {
                          return (
                            <td key={c.key} className="px-3 py-2.5 whitespace-nowrap">
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
                          <td key={c.key} className="px-3 py-2.5 text-center font-mono text-gray-800">
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
      )}
    </div>
  )
}

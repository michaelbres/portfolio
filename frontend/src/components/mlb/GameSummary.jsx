import { useState, useEffect, useRef } from 'react'
import { mlb } from '../../lib/api'
import { pitchColor } from '../../lib/pitchColors'

const LINE_COLS = [
  { key: 'pa',           label: 'PA',      title: 'Plate appearances (batters faced)' },
  { key: 'k',            label: 'K',       title: 'Strikeouts' },
  { key: 'bb',           label: 'BB',      title: 'Walks' },
  { key: 'hits',         label: 'H',       title: 'Hits allowed' },
  { key: 'hr',           label: 'HR',      title: 'Home runs allowed' },
  { key: 'hbp',          label: 'HBP',     title: 'Hit by pitch' },
  { key: 'total_pitches',label: 'Pitches', title: 'Total pitches thrown' },
  { key: 'whiffs',       label: 'Whiffs',  title: 'Swinging strikes' },
  { key: 'strike_pct',   label: 'Strike%', title: 'Strike percentage', fmt: (v) => v != null ? v + '%' : '–' },
]

const ARSENAL_COLS = [
  { key: 'pitch_name', label: 'Pitch',   fmt: null },
  { key: 'count',      label: 'Count',   fmt: null },
  { key: 'usage_pct',  label: 'Pitch%',  fmt: (v) => v + '%' },
  { key: 'avg_velo',   label: 'Velo',    fmt: (v) => v?.toFixed(1) ?? '–' },
  { key: 'avg_spin',   label: 'Spin',    fmt: (v) => v ? Math.round(v) : '–' },
  { key: 'avg_hb',     label: 'HB',      fmt: (v) => v != null ? v.toFixed(1) + '"' : '–' },
  { key: 'avg_ivb',    label: 'IVB',     fmt: (v) => v != null ? v.toFixed(1) + '"' : '–' },
  { key: 'zone_pct',   label: 'Zone%',   fmt: (v) => v != null ? v + '%' : '–' },
  { key: 'chase_pct',  label: 'Chase%',  fmt: (v) => v != null ? v + '%' : '–' },
  { key: 'whiff_pct',  label: 'Whiff%',  fmt: (v) => v != null ? v + '%' : '–' },
  { key: 'avg_xwoba',  label: 'xwOBA',   fmt: (v) => v?.toFixed(3) ?? '–' },
]

export default function GameSummary({ season }) {
  const [search, setSearch]         = useState('')
  const [pitcherResults, setPitcherResults] = useState([])
  const [selectedPitcher, setSelectedPitcher] = useState(null)
  const [games, setGames]           = useState([])
  const [selectedGame, setSelectedGame] = useState(null)
  const [summary, setSummary]       = useState(null)
  const [loading, setLoading]       = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  const debounceRef = useRef(null)
  const wrapperRef = useRef(null)

  // Close dropdown on outside click
  useEffect(() => {
    function onClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  // Debounced pitcher search
  useEffect(() => {
    if (!search.trim()) { setPitcherResults([]); setShowDropdown(false); return }
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await mlb.pitchers({ search: search.trim(), season })
        setPitcherResults(res.data.slice(0, 10))
        setShowDropdown(true)
      } catch { /* ignore */ }
    }, 300)
  }, [search, season])

  async function selectPitcher(pitcher) {
    setSelectedPitcher(pitcher)
    setSearch(pitcher.pitcher_name)
    setShowDropdown(false)
    setPitcherResults([])
    setSelectedGame(null)
    setSummary(null)
    setLoading(true)
    try {
      const res = await mlb.pitcherGames(pitcher.pitcher_id, { season })
      setGames(res.data)
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }

  async function selectGame(game) {
    setSelectedGame(game)
    setSummary(null)
    setLoading(true)
    try {
      const res = await mlb.pitcherGameSummary(selectedPitcher.pitcher_id, game.game_pk)
      setSummary(res.data)
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }

  function gameLabel(g) {
    const opp = g.home_team === (selectedPitcher?.team) ? g.away_team : g.home_team
    return `${g.game_date}  ${g.away_team} @ ${g.home_team}  (${g.total_pitches} pitches)`
  }

  return (
    <div className="space-y-6">
      {/* Step 1: Pitcher search */}
      <div className="bg-white border border-gray-200 rounded p-4">
        <p className="text-xs font-sans text-gray-500 uppercase tracking-wider mb-2">Search Pitcher</p>
        <div className="relative" ref={wrapperRef}>
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setSelectedPitcher(null); setGames([]); setSummary(null) }}
            placeholder="e.g. Gerrit Cole"
            className="border border-gray-300 rounded px-3 py-2 text-sm font-sans w-72 focus:outline-none focus:border-sv-blue"
          />
          {showDropdown && pitcherResults.length > 0 && (
            <ul className="absolute z-10 left-0 top-full mt-1 w-72 bg-white border border-gray-200 rounded shadow-lg text-sm font-sans">
              {pitcherResults.map((p) => (
                <li
                  key={p.pitcher_id}
                  onMouseDown={() => selectPitcher(p)}
                  className="px-3 py-2 hover:bg-gray-100 cursor-pointer flex justify-between items-center"
                >
                  <span>{p.pitcher_name}</span>
                  <span className="text-xs text-gray-400">{p.p_throws}HP · {p.total_pitches} pitches</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Step 2: Game picker */}
      {selectedPitcher && (
        <div className="bg-white border border-gray-200 rounded p-4">
          <p className="text-xs font-sans text-gray-500 uppercase tracking-wider mb-2">Select Game</p>
          {loading && !summary ? (
            <p className="text-sm text-gray-400 font-sans animate-pulse">Loading games…</p>
          ) : games.length === 0 ? (
            <p className="text-sm text-gray-400 font-sans">No games found for this season.</p>
          ) : (
            <select
              value={selectedGame?.game_pk ?? ''}
              onChange={(e) => {
                const g = games.find((x) => String(x.game_pk) === e.target.value)
                if (g) selectGame(g)
              }}
              className="border border-gray-300 rounded px-2 py-1.5 text-sm font-sans w-full max-w-md focus:outline-none focus:border-sv-blue"
            >
              <option value="">— choose a game —</option>
              {games.map((g) => (
                <option key={g.game_pk} value={g.game_pk}>{gameLabel(g)}</option>
              ))}
            </select>
          )}
        </div>
      )}

      {/* Step 3: Game summary */}
      {loading && selectedGame && !summary && (
        <p className="text-sm text-gray-400 font-sans animate-pulse px-1">Loading game summary…</p>
      )}

      {summary && (
        <div className="space-y-4">
          {/* Header */}
          <div className="bg-sv-dark rounded px-5 py-4">
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <h2 className="font-bangers text-white text-2xl tracking-wider">{summary.pitcher_name}</h2>
              <span className="text-gray-400 text-sm font-sans">{summary.p_throws}HP</span>
              <span className="text-sv-red font-bangers tracking-wider text-lg">
                {summary.game_date}
              </span>
              <span className="text-gray-300 text-sm font-sans">
                {summary.away_team} @ {summary.home_team}
              </span>
            </div>
          </div>

          {/* Overall line */}
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

          {/* Per-pitch-type breakdown */}
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

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../../../components/Navbar'
import LeaderboardTable from '../../../components/mlb/LeaderboardTable'
import GameSummary from '../../../components/mlb/GameSummary'
import { mlb } from '../../../lib/api'

const TABS = ['Hitting Leaderboard', 'Pitching Leaderboard', 'Game Summary', 'Statcast Search']

// Column definitions for leaderboards
const PITCHING_COLS = [
  { key: 'pitcher_name',    label: 'Pitcher',   description: 'Pitcher name' },
  { key: 'p_throws',        label: 'Throws',    description: 'Arm' },
  { key: 'total_pitches',   label: 'Pitches',   description: 'Total pitches thrown' },
  { key: 'avg_velo',        label: 'vFA',        description: 'Avg fastball velocity', colorScale: true, format: (v) => v?.toFixed(1) },
  { key: 'max_velo',        label: 'maxVelo',   description: 'Max velocity', colorScale: true, format: (v) => v?.toFixed(1) },
  { key: 'avg_spin',        label: 'Spin',      description: 'Avg spin rate', colorScale: true, format: (v) => v ? Math.round(v) : '–' },
  { key: 'avg_extension',   label: 'Ext',       description: 'Avg release extension (ft)', colorScale: true, format: (v) => v?.toFixed(1) },
  { key: 'avg_pfx_x',       label: 'HB',        description: 'Avg horizontal break (ft)', colorScale: false, format: (v) => v != null ? (v * 12).toFixed(1) + '"' : '–' },
  { key: 'avg_pfx_z',       label: 'IVB',       description: 'Avg induced vertical break (ft)', colorScale: true, format: (v) => v != null ? (v * 12).toFixed(1) + '"' : '–' },
  { key: 'whiff_rate',      label: 'Whiff%',    description: 'Swinging strike rate', colorScale: true, format: (v) => v != null ? v.toFixed(1) + '%' : '–' },
  { key: 'avg_xwoba_against', label: 'xwOBA',  description: 'Avg xwOBA against', colorScale: true, higherIsBetter: false, format: (v) => v?.toFixed(3) },
]

const HITTING_COLS = [
  { key: 'batter_name',     label: 'Batter',    description: 'Batter name' },
  { key: 'stand',           label: 'Bats',      description: 'Batter side' },
  { key: 'batted_balls',    label: 'BBE',       description: 'Batted ball events' },
  { key: 'avg_exit_velo',   label: 'EV',        description: 'Avg exit velocity', colorScale: true, format: (v) => v?.toFixed(1) },
  { key: 'max_exit_velo',   label: 'maxEV',     description: 'Max exit velocity', colorScale: true, format: (v) => v?.toFixed(1) },
  { key: 'avg_launch_angle',label: 'LA',        description: 'Avg launch angle', colorScale: false, format: (v) => v?.toFixed(1) + '°' },
  { key: 'avg_distance',    label: 'Dist',      description: 'Avg hit distance (ft)', colorScale: true, format: (v) => v ? Math.round(v) : '–' },
  { key: 'avg_xba',         label: 'xBA',       description: 'Expected batting average', colorScale: true, format: (v) => v?.toFixed(3) },
  { key: 'avg_xwoba',       label: 'xwOBA',     description: 'Expected weighted on-base average', colorScale: true, format: (v) => v?.toFixed(3) },
]

const SEARCH_COLS = [
  { key: 'game_date',     label: 'Date' },
  { key: 'pitcher_name',  label: 'Pitcher' },
  { key: 'batter_name',   label: 'Batter' },
  { key: 'home_team',     label: 'Home' },
  { key: 'away_team',     label: 'Away' },
  { key: 'pitch_name',    label: 'Pitch' },
  { key: 'release_speed', label: 'Velo',   format: (v) => v?.toFixed(1) },
  { key: 'release_spin_rate', label: 'Spin', format: (v) => v ? Math.round(v) : '–' },
  { key: 'pfx_x',         label: 'HB (in)', format: (v) => v != null ? (v * 12).toFixed(1) : '–' },
  { key: 'pfx_z',         label: 'IVB (in)', format: (v) => v != null ? (v * 12).toFixed(1) : '–' },
  { key: 'plate_x',       label: 'pX',      format: (v) => v?.toFixed(2) },
  { key: 'plate_z',       label: 'pZ',      format: (v) => v?.toFixed(2) },
  { key: 'description',   label: 'Result' },
  { key: 'events',        label: 'Event' },
  { key: 'launch_speed',  label: 'EV',      format: (v) => v?.toFixed(1) },
  { key: 'launch_angle',  label: 'LA',      format: (v) => v?.toFixed(1) },
  { key: 'estimated_woba_using_speedangle', label: 'xwOBA', format: (v) => v?.toFixed(3) },
]

export default function MLBDashboard() {
  const [tab, setTab] = useState(0)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [dataStatus, setDataStatus] = useState(null)
  const [teams, setTeams] = useState([])
  const [pitchTypes, setPitchTypes] = useState([])

  // Filter state
  const [filters, setFilters] = useState({
    season: 2026,
    team: '',
    p_throws: '',
    stand: '',
    pitch_type: '',
    min_pitches: 100,
    min_batted_balls: 25,
    pitcher_search: '',
    batter_search: '',
    sort_by: '',
    sort_dir: 'desc',
    limit: 100,
    offset: 0,
  })

  const setFilter = (key, val) => setFilters((f) => ({ ...f, [key]: val, offset: 0 }))

  useEffect(() => {
    mlb.dataStatus().then((r) => setDataStatus(r.data)).catch(() => {})
    mlb.teams({ season: 2026 }).then((r) => setTeams(r.data)).catch(() => {})
    mlb.pitchTypes().then((r) => setPitchTypes(r.data)).catch(() => {})
  }, [])

  const fetchData = useCallback(async () => {
    if (tab === 2) return  // GameSummary manages its own data
    setLoading(true)
    try {
      const params = { season: filters.season }
      if (filters.team)     params.team = filters.team
      if (filters.p_throws) params.p_throws = filters.p_throws
      if (filters.stand)    params.stand = filters.stand

      if (tab === 0) {
        params.min_batted_balls = filters.min_batted_balls
        const res = await mlb.leaderboardHitting(params)
        setData(res.data)
        setTotal(res.data.length)
      } else if (tab === 1) {
        params.min_pitches = filters.min_pitches
        const res = await mlb.leaderboardPitching(params)
        setData(res.data)
        setTotal(res.data.length)
      } else {
        if (filters.pitch_type) params.pitch_type = filters.pitch_type
        params.limit = filters.limit
        params.offset = filters.offset
        if (filters.sort_by) { params.sort_by = filters.sort_by; params.sort_dir = filters.sort_dir }
        const res = await mlb.pitches(params)
        setData(res.data.data)
        setTotal(res.data.total)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [tab, filters])

  useEffect(() => { fetchData() }, [fetchData])

  const currentCols = tab === 3 ? SEARCH_COLS : tab === 1 ? PITCHING_COLS : HITTING_COLS

  return (
    <div className="min-h-screen bg-sv-light">
      <Navbar />

      {/* MLB Header */}
      <header className="bg-sv-dark border-b-4 border-sv-red px-6 py-5">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="text-3xl">⚾</span>
              <h1 className="font-bangers text-white text-4xl tracking-wider">MLB STATCAST</h1>
              <span className="bg-sv-red text-white text-xs font-bangers px-2 py-0.5 tracking-wider">2026</span>
            </div>
            <p className="text-gray-400 text-sm font-sans">
              Pitch-by-pitch Statcast data — same source as Baseball Savant
            </p>
          </div>
          {dataStatus && (
            <div className="text-right text-xs text-gray-400 font-sans">
              <div>Last updated: <span className="text-white">{dataStatus.latest_game_date || '–'}</span></div>
              <div>Total pitches: <span className="text-white">{dataStatus.total_pitches?.toLocaleString() || '–'}</span></div>
            </div>
          )}
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Tabs */}
        <div className="flex border-b-2 border-gray-300 mb-6">
          {TABS.map((t, i) => (
            <button
              key={t}
              onClick={() => setTab(i)}
              className={`px-5 py-3 font-bangers tracking-wider text-sm uppercase transition-colors border-b-4 -mb-0.5 ${
                tab === i
                  ? 'border-sv-red text-sv-red bg-white'
                  : 'border-transparent text-gray-500 hover:text-gray-800 bg-transparent'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Filters — hidden on Game Summary tab */}
        {tab !== 2 && (
          <FilterBar
            tab={tab} filters={filters} setFilter={setFilter}
            teams={teams} pitchTypes={pitchTypes}
          />
        )}

        {/* Game Summary tab — self-contained */}
        {tab === 2 && <GameSummary season={filters.season} />}

        {/* Leaderboard / Search tabs */}
        {tab !== 2 && (
          <>
            {/* Results header */}
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-gray-500 font-sans">
                {loading ? 'Loading…' : `${total.toLocaleString()} result${total !== 1 ? 's' : ''}`}
              </span>
              {tab === 3 && (
                <div className="flex gap-2 items-center text-xs font-sans text-gray-500">
                  <button
                    disabled={filters.offset === 0}
                    onClick={() => setFilter('offset', Math.max(0, filters.offset - filters.limit))}
                    className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-100"
                  >
                    ← Prev
                  </button>
                  <span>{Math.floor(filters.offset / filters.limit) + 1} / {Math.ceil(total / filters.limit)}</span>
                  <button
                    disabled={filters.offset + filters.limit >= total}
                    onClick={() => setFilter('offset', filters.offset + filters.limit)}
                    className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-100"
                  >
                    Next →
                  </button>
                </div>
              )}
            </div>

            {/* Table */}
            <div className="bg-white border border-gray-200 rounded shadow-sm overflow-hidden">
              {loading ? (
                <div className="py-20 text-center text-gray-400 font-sans text-sm animate-pulse">
                  Loading Statcast data…
                </div>
              ) : (
                <LeaderboardTable
                  rows={data}
                  columns={currentCols}
                  defaultSort={tab === 1 ? 'avg_velo' : tab === 0 ? 'avg_exit_velo' : 'game_date'}
                  linkTo={tab === 1}
                />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function FilterBar({ tab, filters, setFilter, teams, pitchTypes }) {
  return (
    <div className="bg-white border border-gray-200 rounded p-4 mb-4 flex flex-wrap gap-3 items-end">
      {/* Season */}
      <FilterSelect
        label="Season"
        value={filters.season}
        onChange={(v) => setFilter('season', Number(v))}
        options={[{ value: 2026, label: '2026' }, { value: 2025, label: '2025' }]}
      />

      {/* Team */}
      <FilterSelect
        label="Team"
        value={filters.team}
        onChange={(v) => setFilter('team', v)}
        options={[{ value: '', label: 'All' }, ...teams.map((t) => ({ value: t, label: t }))]}
      />

      {/* Pitcher/Batter Hand */}
      <FilterSelect
        label={tab === 0 ? 'Bats' : 'Throws'}
        value={tab === 0 ? filters.stand : filters.p_throws}
        onChange={(v) => tab === 0 ? setFilter('stand', v) : setFilter('p_throws', v)}
        options={[{ value: '', label: 'All' }, { value: 'R', label: 'R' }, { value: 'L', label: 'L' }]}
      />

      {/* Pitch type (search tab only) */}
      {tab === 3 && (
        <FilterSelect
          label="Pitch Type"
          value={filters.pitch_type}
          onChange={(v) => setFilter('pitch_type', v)}
          options={[
            { value: '', label: 'All' },
            ...pitchTypes.map((pt) => ({ value: pt.code, label: pt.name || pt.code })),
          ]}
        />
      )}

      {/* Min pitches (pitching leaderboard) */}
      {tab === 1 && (
        <FilterInput
          label="Min Pitches"
          type="number"
          value={filters.min_pitches}
          onChange={(v) => setFilter('min_pitches', Number(v))}
        />
      )}

      {/* Min BBE (hitting leaderboard) */}
      {tab === 0 && (
        <FilterInput
          label="Min BBE"
          type="number"
          value={filters.min_batted_balls}
          onChange={(v) => setFilter('min_batted_balls', Number(v))}
        />
      )}

      {/* Rows per page (search tab) */}
      {tab === 3 && (
        <FilterSelect
          label="Rows"
          value={filters.limit}
          onChange={(v) => setFilter('limit', Number(v))}
          options={[
            { value: 50, label: '50' },
            { value: 100, label: '100' },
            { value: 250, label: '250' },
            { value: 500, label: '500' },
          ]}
        />
      )}
    </div>
  )
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-sans text-gray-500 uppercase tracking-wider">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="border border-gray-300 rounded px-2 py-1.5 text-sm font-sans bg-white focus:outline-none focus:border-sv-blue"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}

function FilterInput({ label, type = 'text', value, onChange }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-sans text-gray-500 uppercase tracking-wider">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="border border-gray-300 rounded px-2 py-1.5 text-sm font-sans w-24 focus:outline-none focus:border-sv-blue"
      />
    </div>
  )
}

import { useState, useEffect, useCallback } from 'react'
import Navbar from '../../../components/Navbar'
import GameHRCard from '../../../components/mlb/GameHRCard'
import api from '../../../lib/api'

// ── Date helpers ─────────────────────────────────────────────────────────────

function toLocalDateStr(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function addDays(dateStr, n) {
  const d = new Date(dateStr + 'T12:00:00')
  d.setDate(d.getDate() + n)
  return toLocalDateStr(d)
}

function fmtDisplayDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  })
}

// ── Best edges across all games ──────────────────────────────────────────────

function BestEdges({ games }) {
  const allPlayers = games.flatMap(g =>
    (g.players || []).map(p => ({
      ...p,
      matchup: `${g.away_team} @ ${g.home_team}`,
    }))
  )

  const withEdge = allPlayers
    .filter(p => p.edge_pp != null && p.edge_pp > 0.01)
    .sort((a, b) => b.edge_pp - a.edge_pp)
    .slice(0, 8)

  if (withEdge.length === 0) return null

  return (
    <div className="bento-tile p-5 mb-5">
      <div className="flex items-center gap-2 mb-3">
        <span
          className="text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
          style={{ background: 'rgba(40,205,65,0.08)', color: '#1D9E35' }}
        >
          Best Edges
        </span>
        <span className="text-xs text-mist">Model probability exceeds market</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        {withEdge.map((p, i) => (
          <div
            key={i}
            className="flex items-center justify-between px-3 py-2 rounded-xl"
            style={{ background: 'rgba(0,0,0,0.02)', border: '1px solid rgba(0,0,0,0.04)' }}
          >
            <div className="min-w-0">
              <div className="text-sm font-medium text-snow truncate">{p.player_name}</div>
              <div className="text-xs text-mist">{p.matchup}</div>
            </div>
            <div className="text-right ml-2 shrink-0">
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(40,205,65,0.10)', color: '#1D9E35', border: '1px solid rgba(40,205,65,0.20)' }}
              >
                +{(p.edge_pp * 100).toFixed(1)}pp
              </span>
              <div className="text-xs text-mist mt-0.5">
                {(p.model_hr_prob * 100).toFixed(1)}% vs {p.market_hr_odds > 0 ? `+${p.market_hr_odds}` : p.market_hr_odds}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Component ────────────────────────────────────────────────────────────────

export default function HRFairValue() {
  const [selectedDate, setSelectedDate] = useState(toLocalDateStr(new Date()))
  const [games, setGames] = useState([])
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [lastRun, setLastRun] = useState(null)

  const fetchGames = useCallback(async (date) => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.get('/api/hr-fair-value/games', { params: { game_date: date } })
      setGames(data.games ?? [])
    } catch (e) {
      setError('Failed to load HR data. Make sure the pipeline has been run for this date.')
      setGames([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchGames(selectedDate)
  }, [selectedDate, fetchGames])

  async function runPipeline(force = false) {
    setRunning(true)
    setError(null)
    setLastRun(null)
    try {
      const { data } = await api.post('/api/hr-fair-value/run', null, {
        params: { game_date: selectedDate, force },
      })
      if (data.games_computed > 0) {
        setLastRun(`Computed ${data.games_computed} game(s)`)
      } else if (data.error && data.error.startsWith('All ')) {
        setError(data.error)
      } else if (data.error && data.error.includes('failed')) {
        setLastRun(data.error)
      } else {
        setLastRun(data.error || 'No games found for this date.')
      }
    } catch (e) {
      setError(e?.response?.data?.detail || 'Pipeline run failed. Check server logs.')
    } finally {
      setRunning(false)
      fetchGames(selectedDate)
    }
  }

  const totalPlayers = games.reduce((acc, g) => acc + (g.players?.length || 0), 0)
  const playersWithMarket = games.reduce(
    (acc, g) => acc + (g.players?.filter(p => p.market_hr_odds != null).length || 0), 0
  )

  return (
    <div className="min-h-screen bg-void">
      <Navbar />

      {/* Page header */}
      <div style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
        <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col gap-1.5">
          <div className="flex items-center gap-3">
            <span
              className="text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
              style={{ background: 'rgba(40,205,65,0.08)', color: '#1D9E35' }}
            >
              MLB
            </span>
            <h1
              className="text-snow font-semibold tracking-tight text-2xl"
              style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", Inter, system-ui, sans-serif' }}
            >
              HR Fair Value
            </h1>
          </div>
          <p className="text-sm text-mist max-w-2xl leading-relaxed">
            Player-level anytime home run probabilities. Poisson model using Statcast
            HR/PA rates, pitcher HR-allowed factors, HR-specific park factors, and weather carry.
            Compared against DraftKings/FanDuel market lines via The Odds API.
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Date nav */}
          <div
            className="flex items-center rounded-xl overflow-hidden"
            style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.08)' }}
          >
            <button
              onClick={() => setSelectedDate(addDays(selectedDate, -1))}
              className="px-3 py-2 text-mist hover:text-snow transition-colors duration-150 text-sm"
              style={{ borderRight: '1px solid rgba(0,0,0,0.06)' }}
            >
              &#9664;
            </button>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="px-3 py-2 font-mono text-sm focus:outline-none text-snow"
              style={{ background: 'transparent' }}
            />
            <button
              onClick={() => setSelectedDate(addDays(selectedDate, 1))}
              className="px-3 py-2 text-mist hover:text-snow transition-colors duration-150 text-sm"
              style={{ borderLeft: '1px solid rgba(0,0,0,0.06)' }}
            >
              &#9654;
            </button>
          </div>

          <span className="text-mist text-sm hidden md:block">
            {fmtDisplayDate(selectedDate)}
          </span>

          <div className="ml-auto flex items-center gap-2">
            {lastRun && (
              <span
                className="text-xs px-2.5 py-1 rounded-lg"
                style={{ background: 'rgba(40,205,65,0.08)', color: '#1D9E35', border: '1px solid rgba(40,205,65,0.15)' }}
              >
                {lastRun}
              </span>
            )}
            <button
              onClick={() => runPipeline(false)}
              disabled={running}
              className="px-3.5 py-1.5 rounded-xl text-sm font-medium transition-all duration-150 disabled:opacity-50"
              style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.10)', color: '#1D1D1F' }}
              title="Fetch schedule and compute HR fair values"
            >
              {running ? 'Running...' : 'Run Pipeline'}
            </button>
            <button
              onClick={() => runPipeline(true)}
              disabled={running}
              className="px-3.5 py-1.5 rounded-xl text-sm font-medium transition-all duration-150 disabled:opacity-50"
              style={{ background: 'rgba(40,205,65,0.08)', border: '1px solid rgba(40,205,65,0.20)', color: '#1D9E35' }}
              title="Force recompute even if results already exist"
            >
              Force Recompute
            </button>
          </div>
        </div>

        {/* Legend */}
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-mist">
          <span>
            <span className="text-snow font-medium">HR%</span> = P(at least 1 HR in game)
          </span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>
            <span className="text-snow font-medium">Fair</span> = model American odds (no vig)
          </span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>
            <span className="text-snow font-medium">Edge</span> = model prob − market prob (pp)
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 pb-12">
        {error && (
          <div
            className="mb-4 px-4 py-3 text-sm rounded-xl"
            style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.12)', color: '#DC2626' }}
          >
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-mist text-lg font-light animate-pulse tracking-wide">
              Loading games...
            </div>
          </div>
        ) : games.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="text-mist text-lg font-light">
              No HR data for {fmtDisplayDate(selectedDate)}
            </div>
            <p className="text-sm text-mist" style={{ opacity: 0.6 }}>
              Click <strong className="text-snow font-medium">Run Pipeline</strong> to fetch today's schedule and compute HR fair values.
            </p>
          </div>
        ) : (
          <>
            {/* Summary bar */}
            <div className="mb-3 flex items-center justify-between text-sm text-mist">
              <span>
                {games.length} game{games.length !== 1 ? 's' : ''} — {totalPlayers} batters analyzed
                {playersWithMarket > 0 && (
                  <>, <span style={{ color: '#1D9E35' }}>{playersWithMarket} with market lines</span></>
                )}
              </span>
            </div>

            {/* Best edges */}
            <BestEdges games={games} />

            {/* Game cards */}
            <div className="grid gap-5 grid-cols-1 lg:grid-cols-2">
              {games.map((game) => (
                <GameHRCard key={game.game_pk} game={game} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// /home/user/portfolio/frontend/src/pages/sports/mlb/FairValue.jsx
import { useState, useEffect, useCallback } from 'react'
import Navbar from '../../../components/Navbar'
import GameFairValueCard from '../../../components/mlb/GameFairValueCard'
import api from '../../../lib/api'

// ── Date helpers ──────────────────────────────────────────────────────────────

function toLocalDateStr(d) {
  // Returns YYYY-MM-DD in local time
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

// ── Component ─────────────────────────────────────────────────────────────────

export default function FairValue() {
  const [selectedDate, setSelectedDate] = useState(toLocalDateStr(new Date()))
  const [games, setGames] = useState([])
  const [liveOdds, setLiveOdds] = useState({})   // { game_pk: {home_odds, away_odds, ...} }
  const [liveOddsAt, setLiveOddsAt] = useState(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [lastRun, setLastRun] = useState(null)

  const fetchGames = useCallback(async (date) => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.get('/api/fair-value/games', { params: { game_date: date } })
      setGames(data.games ?? [])
    } catch (e) {
      setError('Failed to load games. Make sure the pipeline has been run for this date.')
      setGames([])
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchLiveOdds = useCallback(async (date) => {
    try {
      const { data } = await api.get('/api/fair-value/live-odds', { params: { game_date: date } })
      if (data.kalshi_available) {
        const byPk = {}
        for (const line of data.lines) {
          byPk[line.game_pk] = line
        }
        setLiveOdds(byPk)
        setLiveOddsAt(new Date())
      }
    } catch (e) {
      // live odds are optional — fail silently
    }
  }, [])

  useEffect(() => {
    fetchGames(selectedDate)
    fetchLiveOdds(selectedDate)
    // Refresh Kalshi odds every 5 minutes
    const interval = setInterval(() => fetchLiveOdds(selectedDate), 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [selectedDate, fetchGames, fetchLiveOdds])

  async function runPipeline(force = false) {
    setRunning(true)
    setError(null)
    setLastRun(null)
    try {
      const { data } = await api.post('/api/fair-value/run', null, {
        params: { game_date: selectedDate, force },
      })
      if (data.games_computed > 0) {
        setLastRun(`Computed ${data.games_computed} game(s)`)
      } else if (data.error && data.error.startsWith('All ')) {
        // All games failed — surface as a real error
        setError(data.error)
      } else if (data.error && data.error.includes('failed')) {
        // Some games failed — show as warning in lastRun
        setLastRun(data.error)
      } else {
        // "Already computed" or no games scheduled — informational
        setLastRun(data.error || 'No games found for this date.')
      }
    } catch (e) {
      setError(e?.response?.data?.detail || 'Pipeline run failed. Check server logs.')
    } finally {
      setRunning(false)
      // Always refresh game list — handles "already computed" case
      fetchGames(selectedDate)
    }
  }

  return (
    <div className="min-h-screen bg-void">
      <Navbar />

      {/* Page header */}
      <div
        className="border-b"
        style={{
          background: '#141414',
          borderColor: 'rgba(255,255,255,0.08)',
        }}
      >
        <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col gap-1.5">
          <div className="flex items-center gap-3">
            <span
              className="text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
              style={{
                background: 'rgba(14,165,233,0.12)',
                color: '#0EA5E9',
                border: '1px solid rgba(14,165,233,0.20)',
              }}
            >
              MLB
            </span>
            <h1
              className="text-snow font-semibold tracking-tight text-2xl"
              style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", Inter, system-ui, sans-serif' }}
            >
              Fair Value Model
            </h1>
          </div>
          <p className="text-sm text-mist max-w-2xl leading-relaxed">
            NegBin-based win probabilities derived from Statcast xFIP, pitch count–adjusted
            starter innings, bullpen fatigue, park factors, and home-field advantage.
            50/50 blend of season-long and last-{5}-start metrics.
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Date nav */}
          <div
            className="flex items-center rounded-xl overflow-hidden"
            style={{
              background: '#1C1C1E',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <button
              onClick={() => setSelectedDate(addDays(selectedDate, -1))}
              className="px-3 py-2 text-mist hover:text-snow transition-colors duration-150 text-sm"
              style={{ borderRight: '1px solid rgba(255,255,255,0.08)' }}
            >
              ◀
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
              style={{ borderLeft: '1px solid rgba(255,255,255,0.08)' }}
            >
              ▶
            </button>
          </div>

          <span className="text-mist text-sm hidden md:block">
            {fmtDisplayDate(selectedDate)}
          </span>

          <div className="ml-auto flex items-center gap-2">
            {lastRun && (
              <span
                className="text-xs px-2.5 py-1 rounded-lg"
                style={{
                  background: 'rgba(16,185,129,0.10)',
                  color: '#10B981',
                  border: '1px solid rgba(16,185,129,0.20)',
                }}
              >
                {lastRun}
              </span>
            )}
            <button
              onClick={() => runPipeline(false)}
              disabled={running}
              className="px-3.5 py-1.5 rounded-xl text-sm font-medium transition-all duration-150 disabled:opacity-50"
              style={{
                background: '#1C1C1E',
                border: '1px solid rgba(255,255,255,0.10)',
                color: '#F5F5F7',
              }}
              title="Fetch schedule and compute fair values"
            >
              {running ? 'Running…' : 'Run Pipeline'}
            </button>
            <button
              onClick={() => runPipeline(true)}
              disabled={running}
              className="px-3.5 py-1.5 rounded-xl text-sm font-medium transition-all duration-150 disabled:opacity-50"
              style={{
                background: 'rgba(14,165,233,0.12)',
                border: '1px solid rgba(14,165,233,0.25)',
                color: '#0EA5E9',
              }}
              title="Force recompute even if results already exist"
            >
              Force Recompute
            </button>
          </div>
        </div>

        {/* Model legend */}
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-mist">
          <span>
            <span className="text-snow font-medium">Fair value odds</span> = no-vig American moneyline
          </span>
          <span className="text-smoke">·</span>
          <span>
            <span className="text-snow font-medium">λ</span> = expected runs (NegBin mean)
          </span>
          <span className="text-smoke">·</span>
          <span
            className="font-medium px-1.5 py-0.5 rounded"
            style={{ background: 'rgba(14,165,233,0.10)', color: '#0EA5E9' }}
          >
            Blue pitch limit
          </span>{' '}
          <span>= manual override active</span>
          <span className="text-smoke">·</span>
          <span>Edit pitch limit and press Enter to recompute instantly</span>
        </div>
      </div>

      {/* Game grid */}
      <div className="max-w-7xl mx-auto px-6 pb-12">
        {error && (
          <div
            className="mb-4 px-4 py-3 text-sm rounded-xl"
            style={{
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.20)',
              color: '#FCA5A5',
            }}
          >
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div
              className="text-mist text-lg font-light animate-pulse tracking-wide"
              style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif' }}
            >
              Loading games…
            </div>
          </div>
        ) : games.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="text-mist text-lg font-light">
              No games found for {fmtDisplayDate(selectedDate)}
            </div>
            <p className="text-sm text-mist" style={{ opacity: 0.6 }}>
              Click <strong className="text-snow font-medium">Run Pipeline</strong> to fetch today's schedule and compute fair values.
            </p>
          </div>
        ) : (
          <>
            <div className="mb-3 flex items-center justify-between text-sm text-mist">
              <span>
                {games.length} game{games.length !== 1 ? 's' : ''} —{' '}
                {games.filter((g) => g.home_lineup_source === 'confirmed').length} confirmed lineups,{' '}
                {Object.keys(liveOdds).length > 0
                  ? (
                    <span style={{ color: '#10B981' }}>
                      {Object.keys(liveOdds).length} live Kalshi lines
                    </span>
                  )
                  : `${games.filter((g) => g.market_source).length} with market lines`
                }
              </span>
              {liveOddsAt && (
                <span className="text-xs text-mist" style={{ opacity: 0.6 }}>
                  Kalshi updated {liveOddsAt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                </span>
              )}
            </div>
            <div className="grid gap-5 grid-cols-1 lg:grid-cols-2">
              {games.map((game) => (
                <GameFairValueCard
                  key={game.game_pk}
                  game={game}
                  liveOdds={liveOdds[game.game_pk] ?? null}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

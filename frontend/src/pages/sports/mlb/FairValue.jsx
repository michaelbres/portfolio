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

  useEffect(() => {
    fetchGames(selectedDate)
  }, [selectedDate, fetchGames])

  async function runPipeline(force = false) {
    setRunning(true)
    setError(null)
    try {
      const { data } = await api.post('/api/fair-value/run', null, {
        params: { game_date: selectedDate, force },
      })
      setLastRun(`Computed ${data.games_computed} game(s)`)
      await fetchGames(selectedDate)
    } catch (e) {
      setError('Pipeline run failed. Check server logs.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      {/* Page header */}
      <div className="bg-black text-white border-b-4 border-pop-yellow">
        <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col gap-1">
          <div className="flex items-center gap-3">
            <div className="bg-pop-yellow border-2 border-white px-3 py-0.5">
              <span className="font-bangers text-black tracking-widest text-sm">MLB</span>
            </div>
            <h1 className="font-bangers text-pop-yellow tracking-widest text-3xl">
              FAIR VALUE MODEL
            </h1>
          </div>
          <p className="text-sm text-gray-400 max-w-2xl">
            Poisson-based win probabilities derived from Statcast wOBA, pitch count–adjusted
            starter innings, bullpen fatigue, park factors, and home-field advantage.
            50/50 blend of season-long and last-{5}-start metrics.
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Date nav */}
          <div className="flex items-center border-4 border-black bg-white"
               style={{ boxShadow: '3px 3px 0 #000' }}>
            <button
              onClick={() => setSelectedDate(addDays(selectedDate, -1))}
              className="px-3 py-2 font-bangers text-lg hover:bg-pop-yellow border-r-2 border-black transition-colors"
            >
              ◀
            </button>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="px-3 py-2 font-mono text-sm focus:outline-none"
            />
            <button
              onClick={() => setSelectedDate(addDays(selectedDate, 1))}
              className="px-3 py-2 font-bangers text-lg hover:bg-pop-yellow border-l-2 border-black transition-colors"
            >
              ▶
            </button>
          </div>

          <span className="font-bangers tracking-wider text-lg hidden md:block">
            {fmtDisplayDate(selectedDate)}
          </span>

          <div className="ml-auto flex items-center gap-2">
            {lastRun && (
              <span className="text-xs text-green-700 bg-green-100 px-2 py-1 border border-green-400">
                {lastRun}
              </span>
            )}
            <button
              onClick={() => runPipeline(false)}
              disabled={running}
              className="border-2 border-black bg-white px-3 py-1.5 font-bangers tracking-wider text-sm hover:bg-gray-100 disabled:opacity-50 transition-colors"
              style={{ boxShadow: '2px 2px 0 #000' }}
              title="Fetch schedule and compute fair values"
            >
              {running ? 'Running...' : 'Run Pipeline'}
            </button>
            <button
              onClick={() => runPipeline(true)}
              disabled={running}
              className="border-2 border-black bg-pop-yellow px-3 py-1.5 font-bangers tracking-wider text-sm hover:bg-yellow-300 disabled:opacity-50 transition-colors"
              style={{ boxShadow: '2px 2px 0 #000' }}
              title="Force recompute even if results already exist"
            >
              Force Recompute
            </button>
          </div>
        </div>

        {/* Model legend */}
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-600">
          <span>
            <span className="font-bold">Fair value odds</span> = no-vig American moneyline
          </span>
          <span>·</span>
          <span>
            <span className="font-bold">λ</span> = expected runs (Poisson mean)
          </span>
          <span>·</span>
          <span>
            <span className="font-bold text-pop-yellow bg-black px-1">Yellow pitch limit</span>{' '}
            = manual override active
          </span>
          <span>·</span>
          <span>Edit pitch limit and press Enter to recompute instantly</span>
        </div>
      </div>

      {/* Game grid */}
      <div className="max-w-7xl mx-auto px-6 pb-12">
        {error && (
          <div className="mb-4 bg-red-50 border-2 border-red-500 px-4 py-3 text-red-800 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="font-bangers text-2xl tracking-widest animate-pulse">
              Loading games...
            </div>
          </div>
        ) : games.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="font-bangers text-2xl tracking-widest text-gray-400">
              No games found for {fmtDisplayDate(selectedDate)}
            </div>
            <p className="text-sm text-gray-500">
              Click <strong>Run Pipeline</strong> to fetch today's schedule and compute fair values.
            </p>
          </div>
        ) : (
          <>
            <div className="mb-3 text-sm text-gray-500">
              {games.length} game{games.length !== 1 ? 's' : ''} —{' '}
              {games.filter((g) => g.home_lineup_source === 'confirmed').length} confirmed lineups,{' '}
              {games.filter((g) => g.market_source).length} with market lines
            </div>
            <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
              {games.map((game) => (
                <GameFairValueCard key={game.game_pk} game={game} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

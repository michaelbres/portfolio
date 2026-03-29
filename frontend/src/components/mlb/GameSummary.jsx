import { useState, useEffect, useRef } from 'react'
import { mlb } from '../../lib/api'
import PitcherCard from './PitcherCard'

function formatDateLabel(dateStr) {
  const [y, m, d] = dateStr.split('-')
  const dt = new Date(Number(y), Number(m) - 1, Number(d))
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function groupByGame(pitchers) {
  const map = new Map()
  for (const p of pitchers) {
    if (!map.has(p.game_pk)) map.set(p.game_pk, { home: p.home_team, away: p.away_team, pitchers: [] })
    map.get(p.game_pk).pitchers.push(p)
  }
  return [...map.values()].sort((a, b) =>
    `${a.away}${a.home}`.localeCompare(`${b.away}${b.home}`)
  )
}

export default function GameSummary({ season }) {
  const [dates, setDates]               = useState([])
  const [selectedDate, setSelectedDate] = useState(null)
  const [gamePitchers, setGamePitchers] = useState([])
  const [loadingDates, setLoadingDates] = useState(false)
  const [loadingPitchers, setLoadingPitchers] = useState(false)
  const [cardSummary, setCardSummary]   = useState(null)
  const [loadingCard, setLoadingCard]   = useState(false)
  const [norms, setNorms]               = useState({})
  const dateStripRef = useRef(null)

  // Load league norms once per season (used for heat map coloring in cards)
  useEffect(() => {
    mlb.pitchTypeNorms({ season }).then((r) => setNorms(r.data)).catch(() => {})
  }, [season])

  useEffect(() => {
    setLoadingDates(true)
    setSelectedDate(null)
    setGamePitchers([])
    mlb.gameDates({ season })
      .then((res) => {
        setDates(res.data)
        if (res.data.length) selectDate(res.data[0])
      })
      .catch(() => {})
      .finally(() => setLoadingDates(false))
  }, [season])

  async function selectDate(dateStr) {
    setSelectedDate(dateStr)
    setGamePitchers([])
    setLoadingPitchers(true)
    try {
      const res = await mlb.pitchersByDate({ game_date: dateStr })
      setGamePitchers(res.data)
    } catch { /* ignore */ } finally {
      setLoadingPitchers(false)
    }
  }

  async function openCard(pitcher) {
    setLoadingCard(true)
    try {
      const res = await mlb.pitcherGameSummary(pitcher.pitcher_id, pitcher.game_pk)
      setCardSummary(res.data)
    } catch { /* ignore */ } finally {
      setLoadingCard(false)
    }
  }

  const games = groupByGame(gamePitchers)

  return (
    <>
      {/* Card modal */}
      {cardSummary && (
        <PitcherCard summary={cardSummary} norms={norms} onClose={() => setCardSummary(null)} />
      )}

      <div className="space-y-4">
        {/* Date strip */}
        <div className="bg-white border border-gray-200 rounded p-3">
          <p className="text-xs font-sans text-gray-400 uppercase tracking-wider mb-2">Select Date</p>
          {loadingDates ? (
            <p className="text-sm text-gray-400 font-sans animate-pulse">Loading dates…</p>
          ) : dates.length === 0 ? (
            <p className="text-sm text-gray-400 font-sans">No game data available for this season yet.</p>
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
              {formatDateLabel(selectedDate)} — click a pitcher to see their game
            </p>
            {loadingPitchers ? (
              <p className="text-sm text-gray-400 font-sans animate-pulse">Loading pitchers…</p>
            ) : games.length === 0 ? (
              <p className="text-sm text-gray-400 font-sans">No pitching data for this date.</p>
            ) : (
              <div className="space-y-4">
                {games.map((game) => (
                  <div key={`${game.away}@${game.home}`}>
                    <div className="text-xs font-bangers tracking-wider text-sv-blue mb-1.5">
                      {game.away} @ {game.home}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {game.pitchers.map((p) => (
                        <button
                          key={`${p.pitcher_id}:${p.game_pk}`}
                          onClick={() => openCard(p)}
                          disabled={loadingCard}
                          className="px-3 py-1.5 rounded border border-gray-300 text-xs font-sans text-gray-700 hover:border-sv-red hover:text-sv-red hover:bg-red-50 transition-colors disabled:opacity-50"
                        >
                          {p.pitcher_name}
                          <span className="ml-1.5 text-gray-400">{p.total_pitches}p</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {loadingCard && (
              <p className="text-xs text-gray-400 font-sans animate-pulse mt-3">Loading card…</p>
            )}
          </div>
        )}
      </div>
    </>
  )
}

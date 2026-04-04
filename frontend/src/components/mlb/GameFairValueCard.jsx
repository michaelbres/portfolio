import { useState } from 'react'
import api from '../../lib/api'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtOdds(odds) {
  if (odds == null) return '–'
  return odds > 0 ? `+${odds}` : `${odds}`
}

function fmtPct(p) {
  if (p == null) return '–'
  return (p * 100).toFixed(1) + '%'
}

function fmtWoba(v) {
  if (v == null) return '–'
  return v.toFixed(3)
}

function fmtInn(v) {
  if (v == null) return '–'
  const full = Math.floor(v)
  const third = Math.round((v - full) * 3)
  return third === 0 ? `${full}.0` : `${full}.${third}`
}

function fmtXfip(v) {
  if (v == null) return null
  return v.toFixed(2)
}

function weatherLabel(carry) {
  if (carry == null || Math.abs(carry - 1.0) < 0.005) return null
  const pct = ((carry - 1.0) * 100).toFixed(1)
  return { text: `${carry > 1.0 ? '+' : ''}${pct}% carry`, hot: carry > 1.0 }
}

function edgeLabel(modelOdds, marketOdds) {
  if (modelOdds == null || marketOdds == null) return null
  const toProb = (o) => o > 0 ? 100 / (o + 100) : Math.abs(o) / (Math.abs(o) + 100)
  const modelP  = toProb(modelOdds)
  const marketP = toProb(marketOdds)
  const edge = (modelP - marketP) * 100   // percentage points
  return edge
}

function EdgeBadge({ modelOdds, marketOdds }) {
  const edge = edgeLabel(modelOdds, marketOdds)
  if (edge == null) return null
  const isPos = edge > 0
  return (
    <span className={`text-xs font-bold px-2 py-0.5 border-2 ${
      isPos
        ? 'bg-green-400 border-green-700 text-green-900'
        : 'bg-red-200 border-red-500 text-red-900'
    }`}>
      {isPos ? '+' : ''}{edge.toFixed(1)}pp vs mkt
    </span>
  )
}

// ── Pitch limit input ─────────────────────────────────────────────────────────

function PitchInput({ gamePk, side, defaultLimit, isManual, onUpdate }) {
  const [value, setValue] = useState(String(defaultLimit ?? ''))
  const [saving, setSaving] = useState(false)

  async function handleCommit() {
    const n = parseInt(value, 10)
    if (isNaN(n) || n < 50 || n > 150) return
    if (n === defaultLimit && !isManual) return
    setSaving(true)
    try {
      const { data } = await api.patch(`/api/fair-value/games/${gamePk}/pitch-limit`, {
        side,
        pitch_limit: n,
      })
      onUpdate(data.game)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  async function handleReset() {
    setSaving(true)
    try {
      const { data } = await api.delete(`/api/fair-value/games/${gamePk}/pitch-limit/${side}`)
      setValue(String(data.game[`${side}_pitch_limit`] ?? ''))
      onUpdate(data.game)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex items-center gap-1">
      <input
        type="number"
        min={50}
        max={150}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={handleCommit}
        onKeyDown={(e) => e.key === 'Enter' && handleCommit()}
        disabled={saving}
        className={`w-14 text-center border-2 text-sm font-mono py-0.5 px-1 focus:outline-none focus:border-pop-yellow ${
          isManual ? 'border-pop-yellow bg-yellow-50' : 'border-gray-400 bg-white'
        }`}
        title="Pitch count limit — press Enter or click away to apply"
      />
      {isManual && (
        <button
          onClick={handleReset}
          disabled={saving}
          className="text-xs text-gray-400 hover:text-red-500"
          title="Remove override"
        >
          ✕
        </button>
      )}
    </div>
  )
}

// ── SP row ────────────────────────────────────────────────────────────────────

function SPRow({ label, name, hand, pitchLimit, isManual, projInn,
                 xfipBlended, wobaBlended, paSeason, paRecent, gamePk, side, onUpdate }) {
  const xfip = fmtXfip(xfipBlended)
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-baseline gap-2">
        <span className="text-xs uppercase tracking-wider text-gray-500 w-12 shrink-0">{label}</span>
        <span className="font-bold text-sm truncate">{name || 'TBD'}</span>
        {hand && (
          <span className="text-xs text-gray-500 ml-auto shrink-0">{hand}HP</span>
        )}
      </div>
      <div className="flex items-center gap-3 pl-14">
        <div className="flex items-center gap-1 text-xs text-gray-600">
          <span className="text-gray-400">Limit:</span>
          <PitchInput
            gamePk={gamePk}
            side={side}
            defaultLimit={pitchLimit}
            isManual={isManual}
            onUpdate={onUpdate}
          />
        </div>
        <div className="text-xs text-gray-600">
          <span className="text-gray-400">Inn:</span>{' '}
          <span className="font-mono">{fmtInn(projInn)}</span>
        </div>
        {xfip != null ? (
          <div className="text-xs text-gray-600">
            <span className="text-gray-400">xFIP:</span>{' '}
            <span className="font-mono font-bold">{xfip}</span>
            <span className="text-gray-400 ml-1">(wOBA {fmtWoba(wobaBlended)})</span>
          </div>
        ) : (
          <div className="text-xs text-gray-600">
            <span className="text-gray-400">wOBA:</span>{' '}
            <span className="font-mono">{fmtWoba(wobaBlended)}</span>
            <span className="text-gray-400 ml-1">
              ({paSeason ?? 0}PA full / {paRecent ?? 0} rec)
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Odds panel ────────────────────────────────────────────────────────────────

function OddsPanel({ team, winProb, fairOdds, marketOdds, lambda, isFavorite }) {
  return (
    <div className={`flex flex-col items-center gap-1 px-4 py-3 border-2 min-w-[100px] ${
      isFavorite ? 'border-sv-red bg-red-50' : 'border-gray-300 bg-gray-50'
    }`}>
      <span className="font-bangers tracking-wider text-lg leading-none">{team}</span>
      <span className={`font-bangers text-3xl leading-none ${
        isFavorite ? 'text-sv-red' : 'text-gray-700'
      }`}>
        {fmtOdds(fairOdds)}
      </span>
      <span className="text-xs text-gray-500">{fmtPct(winProb)}</span>
      <span className="text-xs text-gray-400 font-mono">λ {lambda?.toFixed(2)}</span>
      {marketOdds != null && (
        <div className="flex flex-col items-center gap-0.5 mt-1">
          <span className="text-xs text-gray-400">mkt {fmtOdds(marketOdds)}</span>
          <EdgeBadge modelOdds={fairOdds} marketOdds={marketOdds} />
        </div>
      )}
    </div>
  )
}

// ── Main card ─────────────────────────────────────────────────────────────────

export default function GameFairValueCard({ game: initialGame }) {
  const [game, setGame] = useState(initialGame)

  const gameTime = game.game_time_utc
    ? new Date(game.game_time_utc).toLocaleTimeString('en-US', {
        hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
      })
    : null

  const homeIsFav = (game.home_win_prob ?? 0.5) >= 0.5
  const weather   = weatherLabel(game.weather_carry_factor)

  const lineupLabel = (src) => {
    if (src === 'confirmed') return { text: 'Confirmed', cls: 'bg-green-400 text-green-900' }
    if (src === 'projected')  return { text: 'Projected',  cls: 'bg-yellow-300 text-yellow-900' }
    return { text: 'Est.',     cls: 'bg-gray-300 text-gray-700' }
  }

  const homeLineup = lineupLabel(game.home_lineup_source)
  const awayLineup = lineupLabel(game.away_lineup_source)

  return (
    <div className="bg-white border-4 border-black" style={{ boxShadow: '4px 4px 0 #000' }}>
      {/* Header */}
      <div className="flex items-center justify-between bg-black text-white px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="font-bangers tracking-widest text-lg">
            {game.away_team} <span className="text-gray-400">@</span> {game.home_team}
          </span>
          <span className="text-xs text-gray-400">{game.venue}</span>
        </div>
        <div className="flex items-center gap-2">
          {gameTime && <span className="text-xs text-gray-400">{gameTime}</span>}
          {weather && (
            <span className={`text-xs px-2 py-0.5 font-bold ${
              weather.hot ? 'bg-orange-500 text-white' : 'bg-sky-500 text-white'
            }`}>
              {weather.text}
            </span>
          )}
          <span className="text-xs bg-gray-700 px-2 py-0.5">
            PF {game.park_factor?.toFixed(2)}
          </span>
        </div>
      </div>

      <div className="p-4 flex flex-col gap-4">
        {/* Odds row */}
        <div className="flex items-center justify-center gap-4">
          <OddsPanel
            team={game.away_team}
            winProb={game.away_win_prob}
            fairOdds={game.away_fair_odds}
            marketOdds={game.away_market_odds}
            lambda={game.away_lambda}
            isFavorite={!homeIsFav}
          />
          <span className="font-bangers text-2xl text-gray-300">VS</span>
          <OddsPanel
            team={game.home_team}
            winProb={game.home_win_prob}
            fairOdds={game.home_fair_odds}
            marketOdds={game.home_market_odds}
            lambda={game.home_lambda}
            isFavorite={homeIsFav}
          />
        </div>

        {/* Pitcher details */}
        <div className="border-t-2 border-gray-200 pt-3 flex flex-col gap-3">
          <SPRow
            label="Away SP"
            name={game.away_sp_name}
            hand={game.away_sp_hand}
            pitchLimit={game.away_pitch_limit}
            isManual={game.away_pitch_limit_manual}
            projInn={game.away_sp_proj_innings}
            xfipBlended={game.away_sp_xfip_blended}
            wobaBlended={game.away_sp_woba_blended}
            paSeason={game.away_sp_pa_season}
            paRecent={game.away_sp_pa_recent}
            gamePk={game.game_pk}
            side="away"
            onUpdate={setGame}
          />
          <SPRow
            label="Home SP"
            name={game.home_sp_name}
            hand={game.home_sp_hand}
            pitchLimit={game.home_pitch_limit}
            isManual={game.home_pitch_limit_manual}
            projInn={game.home_sp_proj_innings}
            xfipBlended={game.home_sp_xfip_blended}
            wobaBlended={game.home_sp_woba_blended}
            paSeason={game.home_sp_pa_season}
            paRecent={game.home_sp_pa_recent}
            gamePk={game.game_pk}
            side="home"
            onUpdate={setGame}
          />
        </div>

        {/* Lineup + bullpen */}
        <div className="border-t-2 border-gray-200 pt-3 grid grid-cols-2 gap-3 text-xs">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-gray-500 uppercase tracking-wider">{game.away_team} Lineup</span>
              <span className={`px-1.5 py-0.5 text-xs font-bold border ${awayLineup.cls}`}>
                {awayLineup.text}
              </span>
            </div>
            <div className="font-mono">
              wOBA <span className="font-bold">{fmtWoba(game.away_lineup_woba)}</span>
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-gray-500 uppercase tracking-wider">{game.home_team} Lineup</span>
              <span className={`px-1.5 py-0.5 text-xs font-bold border ${homeLineup.cls}`}>
                {homeLineup.text}
              </span>
            </div>
            <div className="font-mono">
              wOBA <span className="font-bold">{fmtWoba(game.home_lineup_woba)}</span>
            </div>
          </div>

          {/* Bullpen */}
          <div className="flex flex-col gap-0.5">
            <span className="text-gray-500 uppercase tracking-wider">{game.away_team} Bullpen</span>
            <div className="font-mono">
              wOBA {fmtWoba(game.away_bp_woba_fatigued)}
              {game.away_bp_woba_fatigued !== game.away_bp_woba_raw && (
                <span className="text-gray-400 ml-1">
                  (raw {fmtWoba(game.away_bp_woba_raw)})
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-gray-500 uppercase tracking-wider">{game.home_team} Bullpen</span>
            <div className="font-mono">
              wOBA {fmtWoba(game.home_bp_woba_fatigued)}
              {game.home_bp_woba_fatigued !== game.home_bp_woba_raw && (
                <span className="text-gray-400 ml-1">
                  (raw {fmtWoba(game.home_bp_woba_raw)})
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-gray-400 border-t-2 border-gray-100 pt-2">
          <span>v{game.model_version}</span>
          <div className="flex items-center gap-2">
            {game.market_source && (
              <span className="uppercase tracking-wider">
                25% {game.market_source} blend
              </span>
            )}
          </div>
          {game.computed_at && (
            <span>
              updated {new Date(game.computed_at).toLocaleTimeString('en-US', {
                hour: 'numeric', minute: '2-digit',
              })}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

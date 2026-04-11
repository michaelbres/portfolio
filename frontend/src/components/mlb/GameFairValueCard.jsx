// /home/user/portfolio/frontend/src/components/mlb/GameFairValueCard.jsx
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
    <span
      className="text-xs font-semibold px-2 py-0.5 rounded-full"
      style={
        isPos
          ? { background: 'rgba(16,185,129,0.15)', color: '#34D399', border: '1px solid rgba(16,185,129,0.25)' }
          : { background: 'rgba(239,68,68,0.12)', color: '#F87171', border: '1px solid rgba(239,68,68,0.20)' }
      }
    >
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
        className="w-14 text-center text-sm font-mono py-0.5 px-1 focus:outline-none rounded"
        style={
          isManual
            ? {
                border: '1px solid rgba(14,165,233,0.40)',
                background: 'rgba(14,165,233,0.08)',
                color: '#38BDF8',
              }
            : {
                border: '1px solid rgba(255,255,255,0.12)',
                background: '#1C1C1E',
                color: '#F5F5F7',
              }
        }
        title="Pitch count limit — press Enter or click away to apply"
      />
      {isManual && (
        <button
          onClick={handleReset}
          disabled={saving}
          className="text-xs text-mist hover:text-red-400 transition-colors duration-150"
          title="Remove override"
        >
          ✕
        </button>
      )}
    </div>
  )
}

// ── SP row ────────────────────────────────────────────────────────────────────

// Data confidence: pa_season proxy for how much Statcast history we have.
// < 100 PA ≈ < 23 IP  → heavy regression, flag as thin
// 100-299 PA          → partial, flag as limited
// 300+ PA             → good sample
function dataConfidence(paSeason) {
  if (paSeason == null || paSeason === 0) return 'none'
  if (paSeason < 100)  return 'thin'
  if (paSeason < 300)  return 'limited'
  return 'good'
}

function SPRow({ label, name, hand, pitchLimit, isManual, projInn,
                 xfipBlended, wobaBlended, paSeason, paRecent, gamePk, side, onUpdate }) {
  const xfip  = fmtXfip(xfipBlended)
  const conf  = dataConfidence(paSeason)

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-baseline gap-2">
        <span className="text-xs uppercase tracking-wider text-mist w-12 shrink-0">{label}</span>
        <span className="font-semibold text-sm text-snow truncate">{name || 'TBD'}</span>
        {conf === 'none' && (
          <span
            className="text-xs px-1.5 py-0.5 rounded font-bold"
            style={{
              background: 'rgba(239,68,68,0.15)',
              border: '1px solid rgba(239,68,68,0.25)',
              color: '#F87171',
            }}
          >
            NO DATA
          </span>
        )}
        {conf === 'thin' && (
          <span
            className="text-xs px-1.5 py-0.5 rounded"
            style={{
              background: 'rgba(249,115,22,0.12)',
              border: '1px solid rgba(249,115,22,0.20)',
              color: '#FB923C',
            }}
          >
            thin sample
          </span>
        )}
        {conf === 'limited' && (
          <span
            className="text-xs px-1.5 py-0.5 rounded"
            style={{
              background: 'rgba(234,179,8,0.10)',
              border: '1px solid rgba(234,179,8,0.18)',
              color: '#FCD34D',
            }}
          >
            limited
          </span>
        )}
        {hand && (
          <span className="text-xs text-mist ml-auto shrink-0">{hand}HP</span>
        )}
      </div>
      <div className="flex items-center gap-3 pl-14">
        <div className="flex items-center gap-1 text-xs text-mist">
          <span className="text-mist" style={{ opacity: 0.6 }}>Limit:</span>
          <PitchInput
            gamePk={gamePk}
            side={side}
            defaultLimit={pitchLimit}
            isManual={isManual}
            onUpdate={onUpdate}
          />
        </div>
        <div className="text-xs text-mist">
          <span style={{ opacity: 0.6 }}>Inn:</span>{' '}
          <span className="font-mono text-snow">{fmtInn(projInn)}</span>
        </div>
        {xfip != null ? (
          <div className="text-xs text-mist">
            <span style={{ opacity: 0.6 }}>xFIP:</span>{' '}
            <span className={`font-mono font-semibold ${
              conf !== 'good' ? 'text-orange-400' : 'text-snow'
            }`}>{xfip}</span>
            <span className="text-mist ml-1" style={{ opacity: 0.6 }}>({paSeason ?? 0} PA)</span>
          </div>
        ) : (
          <div className="text-xs text-mist">
            <span style={{ opacity: 0.6 }}>wOBA:</span>{' '}
            <span className="font-mono text-snow">{fmtWoba(wobaBlended)}</span>
            <span className="text-mist ml-1" style={{ opacity: 0.6 }}>({paSeason ?? 0} PA)</span>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Odds panel ────────────────────────────────────────────────────────────────

// ── Totals row ────────────────────────────────────────────────────────────────

function TotalsRow({ modelTotal, kalshiLine, kalshiOverPrice, modelOverProb }) {
  const hasKalshi = kalshiLine != null && kalshiOverPrice != null

  // Direction signal: model says over/under is more likely than Kalshi prices
  let signal = null
  if (hasKalshi && modelOverProb != null) {
    const diff = modelOverProb - kalshiOverPrice
    if (Math.abs(diff) >= 0.04) {
      signal = diff > 0
        ? { text: `Model leans OVER ${kalshiLine}`, color: '#34D399' }
        : { text: `Model leans UNDER ${kalshiLine}`, color: '#F87171' }
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
      <span className="text-mist uppercase tracking-wider" style={{ opacity: 0.7 }}>Totals</span>

      {/* Model total */}
      <div className="flex items-center gap-1 text-mist">
        <span style={{ opacity: 0.6 }}>Model:</span>
        <span className="font-mono font-semibold text-snow">{modelTotal?.toFixed(1)} runs</span>
      </div>

      {/* Kalshi line */}
      {hasKalshi ? (
        <>
          <div className="flex items-center gap-1 text-mist">
            <span style={{ opacity: 0.6 }}>Kalshi O/U:</span>
            <span className="font-mono font-semibold text-snow">{kalshiLine}</span>
          </div>
          <div className="flex items-center gap-1 text-mist">
            <span style={{ opacity: 0.6 }}>Over:</span>
            <span className="font-mono text-snow">
              {fmtOdds(Math.round(kalshiOverPrice >= 0.5
                ? -kalshiOverPrice / (1 - kalshiOverPrice) * 100
                : (1 - kalshiOverPrice) / kalshiOverPrice * 100))}
            </span>
          </div>
          {modelOverProb != null && (
            <div className="flex items-center gap-1 text-mist">
              <span style={{ opacity: 0.6 }}>Model over:</span>
              <span className="font-mono text-snow">{fmtPct(modelOverProb)}</span>
            </div>
          )}
          {signal && (
            <span
              className="font-semibold px-2 py-0.5 rounded-full text-[11px]"
              style={{
                background: signal.color === '#34D399'
                  ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.10)',
                border: `1px solid ${signal.color}33`,
                color: signal.color,
              }}
            >
              {signal.text}
            </span>
          )}
        </>
      ) : (
        <span className="text-mist" style={{ opacity: 0.5 }}>no Kalshi line</span>
      )}
    </div>
  )
}


function movementArrow(openingOdds, currentOdds) {
  // Returns null if no movement, or {dir, delta, color} for display
  if (openingOdds == null || currentOdds == null) return null
  const toProb = (o) => o > 0 ? 100 / (o + 100) : Math.abs(o) / (Math.abs(o) + 100)
  const delta = (toProb(currentOdds) - toProb(openingOdds)) * 100  // pp
  if (Math.abs(delta) < 0.5) return null
  return {
    dir: delta > 0 ? '▲' : '▼',
    delta: Math.abs(delta).toFixed(1),
    color: delta > 0 ? '#34D399' : '#F87171',  // green = moved toward this team
  }
}

function OddsPanel({ team, winProb, fairOdds, marketOdds, openingOdds, lambda, isFavorite, isLive }) {
  const mv = movementArrow(openingOdds, marketOdds)
  return (
    <div
      className="flex flex-col items-center gap-1 px-4 py-3 rounded-xl min-w-[100px]"
      style={
        isFavorite
          ? {
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.20)',
            }
          : {
              background: '#1C1C1E',
              border: '1px solid rgba(255,255,255,0.08)',
            }
      }
    >
      <span className="font-semibold text-snow text-base leading-none tracking-tight">{team}</span>
      <span
        className="font-semibold text-2xl leading-none mt-1"
        style={{ color: isFavorite ? '#F87171' : '#F5F5F7' }}
      >
        {fmtOdds(fairOdds)}
      </span>
      <span className="text-xs text-mist">{fmtPct(winProb)}</span>
      <span className="text-xs text-mist font-mono" style={{ opacity: 0.6 }}>λ {lambda?.toFixed(2)}</span>
      {marketOdds != null && (
        <div
          className="flex flex-col items-center gap-0.5 mt-1 pt-1 w-full"
          style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}
        >
          <div className="flex items-center gap-1">
            {isLive && (
              <span
                className="text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none"
                style={{ background: 'rgba(14,165,233,0.15)', color: '#0EA5E9' }}
              >
                LIVE
              </span>
            )}
            <span className="text-xs text-mist font-mono font-semibold">{fmtOdds(marketOdds)}</span>
            {mv && (
              <span className="text-[10px] font-bold" style={{ color: mv.color }}>
                {mv.dir}{mv.delta}pp
              </span>
            )}
          </div>
          {openingOdds != null && openingOdds !== marketOdds && (
            <span className="text-[10px] text-mist" style={{ opacity: 0.55 }}>
              open {fmtOdds(openingOdds)}
            </span>
          )}
          <EdgeBadge modelOdds={fairOdds} marketOdds={marketOdds} />
        </div>
      )}
    </div>
  )
}

// ── Main card ─────────────────────────────────────────────────────────────────

export default function GameFairValueCard({ game: initialGame, liveOdds = null }) {
  const [game, setGame] = useState(initialGame)

  // Use live Kalshi odds when available, fall back to stored market odds
  const homeMarketOdds = liveOdds?.home_odds ?? game.home_market_odds
  const awayMarketOdds = liveOdds?.away_odds ?? game.away_market_odds
  const isLive = liveOdds != null

  const homeOpeningOdds = game.opening_home_odds
  const awayOpeningOdds = game.opening_away_odds

  const gameTime = game.game_time_utc
    ? new Date(game.game_time_utc).toLocaleTimeString('en-US', {
        hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
      })
    : null

  const homeIsFav = (game.home_win_prob ?? 0.5) >= 0.5
  const weather   = weatherLabel(game.weather_carry_factor)

  const lineupLabel = (src) => {
    if (src === 'confirmed') return {
      text: 'Confirmed',
      style: { background: 'rgba(16,185,129,0.12)', color: '#34D399', border: '1px solid rgba(16,185,129,0.22)' },
    }
    if (src === 'projected') return {
      text: 'Projected',
      style: { background: 'rgba(234,179,8,0.10)', color: '#FCD34D', border: '1px solid rgba(234,179,8,0.18)' },
    }
    return {
      text: 'Est.',
      style: { background: 'rgba(255,255,255,0.06)', color: '#86868B', border: '1px solid rgba(255,255,255,0.10)' },
    }
  }

  const homeLineup = lineupLabel(game.home_lineup_source)
  const awayLineup = lineupLabel(game.away_lineup_source)

  return (
    <div
      className="bg-surface rounded-2xl overflow-hidden"
      style={{
        border: '1px solid rgba(255,255,255,0.08)',
        boxShadow: '0 1px 3px rgba(0,0,0,0.5)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{ background: '#1C1C1E', borderBottom: '1px solid rgba(255,255,255,0.06)' }}
      >
        <div className="flex items-center gap-3">
          <span className="font-semibold text-snow text-sm tracking-tight">
            {game.away_team} <span className="text-mist font-normal">@</span> {game.home_team}
          </span>
          <span className="text-xs text-mist" style={{ opacity: 0.7 }}>{game.venue}</span>
        </div>
        <div className="flex items-center gap-2">
          {gameTime && <span className="text-xs text-mist">{gameTime}</span>}
          {weather && (
            <span
              className="text-xs px-2 py-0.5 rounded-full font-semibold"
              style={
                weather.hot
                  ? { background: 'rgba(249,115,22,0.15)', color: '#FB923C' }
                  : { background: 'rgba(14,165,233,0.12)', color: '#38BDF8' }
              }
            >
              {weather.text}
            </span>
          )}
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{
              background: 'rgba(255,255,255,0.06)',
              color: '#86868B',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
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
            marketOdds={awayMarketOdds}
            openingOdds={awayOpeningOdds}
            lambda={game.away_lambda}
            isFavorite={!homeIsFav}
            isLive={isLive}
          />
          <span className="text-xl text-mist font-light" style={{ opacity: 0.4 }}>vs</span>
          <OddsPanel
            team={game.home_team}
            winProb={game.home_win_prob}
            fairOdds={game.home_fair_odds}
            marketOdds={homeMarketOdds}
            openingOdds={homeOpeningOdds}
            lambda={game.home_lambda}
            isFavorite={homeIsFav}
            isLive={isLive}
          />
        </div>

        {/* Pitcher details */}
        <div
          className="pt-3 flex flex-col gap-3"
          style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
        >
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
        <div
          className="pt-3 grid grid-cols-2 gap-3 text-xs"
          style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
        >
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-mist uppercase tracking-wider" style={{ opacity: 0.7 }}>
                {game.away_team} Lineup
              </span>
              <span className="px-1.5 py-0.5 text-xs font-semibold rounded" style={awayLineup.style}>
                {awayLineup.text}
              </span>
            </div>
            <div className="font-mono text-mist">
              wOBA <span className="font-bold text-snow">{fmtWoba(game.away_lineup_woba)}</span>
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-mist uppercase tracking-wider" style={{ opacity: 0.7 }}>
                {game.home_team} Lineup
              </span>
              <span className="px-1.5 py-0.5 text-xs font-semibold rounded" style={homeLineup.style}>
                {homeLineup.text}
              </span>
            </div>
            <div className="font-mono text-mist">
              wOBA <span className="font-bold text-snow">{fmtWoba(game.home_lineup_woba)}</span>
            </div>
          </div>

          {/* Bullpen */}
          <div className="flex flex-col gap-0.5">
            <span className="text-mist uppercase tracking-wider" style={{ opacity: 0.7 }}>
              {game.away_team} Bullpen
            </span>
            <div className="font-mono text-mist">
              wOBA {fmtWoba(game.away_bp_woba_fatigued)}
              {game.away_bp_woba_fatigued !== game.away_bp_woba_raw && (
                <span className="text-mist ml-1" style={{ opacity: 0.5 }}>
                  (raw {fmtWoba(game.away_bp_woba_raw)})
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-mist uppercase tracking-wider" style={{ opacity: 0.7 }}>
              {game.home_team} Bullpen
            </span>
            <div className="font-mono text-mist">
              wOBA {fmtWoba(game.home_bp_woba_fatigued)}
              {game.home_bp_woba_fatigued !== game.home_bp_woba_raw && (
                <span className="text-mist ml-1" style={{ opacity: 0.5 }}>
                  (raw {fmtWoba(game.home_bp_woba_raw)})
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Totals */}
        {game.model_total != null && (
          <div
            className="pt-3"
            style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
          >
            <TotalsRow
              modelTotal={game.model_total}
              kalshiLine={game.kalshi_total_line}
              kalshiOverPrice={game.kalshi_over_price}
              modelOverProb={game.model_over_prob}
            />
          </div>
        )}

        {/* Footer */}
        <div
          className="flex items-center justify-between text-xs text-mist pt-2"
          style={{ borderTop: '1px solid rgba(255,255,255,0.06)', opacity: 0.7 }}
        >
          <span>v{game.model_version}</span>
          <div className="flex items-center gap-2">
            {isLive ? (
              <span className="flex items-center gap-1">
                <span
                  className="font-bold text-[10px] px-1.5 py-0.5 rounded-full"
                  style={{ background: 'rgba(14,165,233,0.15)', color: '#0EA5E9' }}
                >
                  LIVE
                </span>
                <span className="uppercase tracking-wider">kalshi</span>
              </span>
            ) : game.market_source ? (
              <span className="uppercase tracking-wider">vs {game.market_source}</span>
            ) : null}
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

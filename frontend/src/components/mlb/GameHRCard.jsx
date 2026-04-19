import { useState } from 'react'

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtOdds(odds) {
  if (odds == null) return '–'
  return odds > 0 ? `+${odds}` : `${odds}`
}

function fmtPct(p) {
  if (p == null) return '–'
  return (p * 100).toFixed(1) + '%'
}

function fmtTime(utcStr) {
  if (!utcStr) return ''
  try {
    const d = new Date(utcStr)
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  } catch {
    return ''
  }
}

function EdgeBadge({ edge }) {
  if (edge == null) return null
  const pp = (edge * 100)
  if (Math.abs(pp) < 0.5) return null
  const isPos = pp > 0
  return (
    <span
      className="text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap"
      style={
        isPos
          ? { background: 'rgba(40,205,65,0.10)', color: '#1D9E35', border: '1px solid rgba(40,205,65,0.20)' }
          : { background: 'rgba(239,68,68,0.08)', color: '#DC2626', border: '1px solid rgba(239,68,68,0.15)' }
      }
    >
      {isPos ? '+' : ''}{pp.toFixed(1)}pp
    </span>
  )
}

function HRProbBadge({ prob }) {
  if (prob == null) return <span className="text-mist">–</span>
  const pct = prob * 100
  // Color intensity based on probability
  let color, bg, border
  if (pct >= 12) {
    color = '#1D9E35'; bg = 'rgba(40,205,65,0.10)'; border = 'rgba(40,205,65,0.20)'
  } else if (pct >= 8) {
    color = '#0066CC'; bg = 'rgba(0,102,204,0.08)'; border = 'rgba(0,102,204,0.15)'
  } else if (pct >= 5) {
    color = '#86868B'; bg = 'rgba(134,134,139,0.08)'; border = 'rgba(134,134,139,0.12)'
  } else {
    color = '#86868B'; bg = 'transparent'; border = 'transparent'
  }
  return (
    <span
      className="text-xs font-semibold px-2 py-0.5 rounded-full"
      style={{ color, background: bg, border: `1px solid ${border}` }}
    >
      {pct.toFixed(1)}%
    </span>
  )
}

// ── Player row ──────────────────────────────────────────────────────────────

function PlayerRow({ player }) {
  const handLabel = player.batter_hand === 'L' ? 'L' : player.batter_hand === 'S' ? 'S' : 'R'

  return (
    <div
      className="flex items-center gap-2 py-1.5 px-2 rounded-lg transition-colors duration-150"
      style={{ borderBottom: '1px solid rgba(0,0,0,0.04)' }}
    >
      {/* Order */}
      <span className="text-xs text-mist w-5 text-center font-mono">{player.batting_order}</span>

      {/* Name + hand */}
      <div className="flex-1 min-w-0">
        <span className="text-sm text-snow font-medium truncate block">
          {player.player_name}
        </span>
      </div>
      <span
        className="text-xs px-1.5 py-0.5 rounded"
        style={{ background: 'rgba(0,0,0,0.04)', color: '#86868B' }}
      >
        {handLabel}
      </span>

      {/* Model prob */}
      <div className="text-right w-16">
        <HRProbBadge prob={player.model_hr_prob} />
      </div>

      {/* Fair odds */}
      <div className="text-right w-14">
        <span className="text-xs font-mono text-snow">{fmtOdds(player.fair_hr_odds)}</span>
      </div>

      {/* Market odds */}
      <div className="text-right w-14">
        <span className="text-xs font-mono text-mist">
          {player.market_hr_odds != null ? fmtOdds(player.market_hr_odds) : '–'}
        </span>
      </div>

      {/* Edge */}
      <div className="text-right w-16">
        <EdgeBadge edge={player.edge_pp} />
      </div>
    </div>
  )
}

// ── Main card ───────────────────────────────────────────────────────────────

export default function GameHRCard({ game }) {
  const [expanded, setExpanded] = useState(true)

  const homePlayers = (game.players || []).filter(p => p.is_home)
  const awayPlayers = (game.players || []).filter(p => !p.is_home)

  const parkLabel = game.park_hr_factor != null
    ? `${game.park_hr_factor > 1 ? '+' : ''}${((game.park_hr_factor - 1) * 100).toFixed(0)}% HR`
    : null

  const weatherLabel = game.weather_hr_factor != null && Math.abs(game.weather_hr_factor - 1.0) >= 0.01
    ? `${game.weather_hr_factor > 1 ? '+' : ''}${((game.weather_hr_factor - 1) * 100).toFixed(0)}% wx`
    : null

  return (
    <div className="bento-tile p-0" style={{ cursor: 'default' }}>
      {/* Header */}
      <div className="px-5 pt-4 pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-snow font-semibold text-lg" style={{ letterSpacing: '-0.01em' }}>
              {game.away_team} <span className="text-mist font-normal">@</span> {game.home_team}
            </span>
            {game.game_time_utc && (
              <span className="text-xs text-mist">{fmtTime(game.game_time_utc)}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {parkLabel && (
              <span
                className="text-xs px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(0,0,0,0.04)', color: '#86868B', border: '1px solid rgba(0,0,0,0.06)' }}
              >
                {parkLabel}
              </span>
            )}
            {weatherLabel && (
              <span
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: game.weather_hr_factor > 1 ? 'rgba(239,68,68,0.06)' : 'rgba(0,102,204,0.06)',
                  color: game.weather_hr_factor > 1 ? '#DC2626' : '#0066CC',
                  border: `1px solid ${game.weather_hr_factor > 1 ? 'rgba(239,68,68,0.12)' : 'rgba(0,102,204,0.12)'}`,
                }}
              >
                {weatherLabel}
              </span>
            )}
          </div>
        </div>

        {/* Venue + pitchers */}
        <div className="flex items-center gap-2 mt-1.5 text-xs text-mist">
          {game.venue && <span>{game.venue}</span>}
          {game.venue && <span style={{ opacity: 0.4 }}>·</span>}
          <span>
            {game.away_sp_name || 'TBD'} ({game.away_sp_hand || '?'}) vs {game.home_sp_name || 'TBD'} ({game.home_sp_hand || '?'})
          </span>
        </div>

        {/* Game totals summary */}
        <div className="flex items-center gap-4 mt-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-mist">Game HR</span>
            <span className="text-sm font-semibold text-snow">
              {game.game_total_hr_lambda?.toFixed(2) ?? '–'} exp
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-mist">{game.away_team}</span>
            <span className="text-sm font-medium text-snow">
              {game.away_team_hr_lambda?.toFixed(2) ?? '–'}
            </span>
            <span className="text-xs text-mist" style={{ opacity: 0.5 }}>
              ({fmtPct(game.away_team_hr_prob)} for 1+)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-mist">{game.home_team}</span>
            <span className="text-sm font-medium text-snow">
              {game.home_team_hr_lambda?.toFixed(2) ?? '–'}
            </span>
            <span className="text-xs text-mist" style={{ opacity: 0.5 }}>
              ({fmtPct(game.home_team_hr_prob)} for 1+)
            </span>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }} />

      {/* Column headers */}
      <div className="px-5 py-2 flex items-center gap-2 text-xs text-mist" style={{ background: 'rgba(0,0,0,0.02)' }}>
        <span className="w-5 text-center">#</span>
        <span className="flex-1">Player</span>
        <span className="w-6" />
        <span className="w-16 text-right">HR%</span>
        <span className="w-14 text-right">Fair</span>
        <span className="w-14 text-right">Market</span>
        <span className="w-16 text-right">Edge</span>
      </div>

      {/* Away team */}
      <div className="px-3">
        <div className="px-2 py-1.5">
          <span
            className="text-xs font-semibold tracking-wider uppercase"
            style={{ color: '#86868B' }}
          >
            {game.away_team}
          </span>
        </div>
        {awayPlayers.map((p, i) => (
          <PlayerRow key={p.player_id || i} player={p} />
        ))}
      </div>

      {/* Divider */}
      <div className="mx-5" style={{ borderTop: '1px solid rgba(0,0,0,0.04)' }} />

      {/* Home team */}
      <div className="px-3 pb-3">
        <div className="px-2 py-1.5">
          <span
            className="text-xs font-semibold tracking-wider uppercase"
            style={{ color: '#86868B' }}
          >
            {game.home_team}
          </span>
        </div>
        {homePlayers.map((p, i) => (
          <PlayerRow key={p.player_id || i} player={p} />
        ))}
      </div>

      {/* Footer */}
      <div
        className="px-5 py-2 flex items-center justify-between text-xs text-mist"
        style={{ background: 'rgba(0,0,0,0.02)', borderTop: '1px solid rgba(0,0,0,0.04)' }}
      >
        <span>v{game.model_version}</span>
        {game.computed_at && (
          <span>
            {new Date(game.computed_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
          </span>
        )}
      </div>
    </div>
  )
}

import { useState } from 'react'
import Navbar from '../components/Navbar'

// ── Math helpers ──────────────────────────────────────────────────────────────

function parseOdds(raw) {
  const n = parseFloat(String(raw).replace(/\s/g, ''))
  return isNaN(n) ? null : n
}

function americanToProb(odds) {
  if (odds === null) return null
  return odds > 0 ? 100 / (odds + 100) : Math.abs(odds) / (Math.abs(odds) + 100)
}

function americanToDecimal(odds) {
  if (odds === null) return null
  return odds > 0 ? odds / 100 + 1 : 100 / Math.abs(odds) + 1
}

function decimalToAmerican(dec) {
  if (dec === null || dec <= 1) return null
  return dec >= 2 ? Math.round((dec - 1) * 100) : Math.round(-100 / (dec - 1))
}

function probToAmerican(prob) {
  if (prob === null || prob <= 0 || prob >= 1) return null
  return prob >= 0.5
    ? Math.round((-prob / (1 - prob)) * 100)
    : Math.round(((1 - prob) / prob) * 100)
}

function fmtAmerican(odds) {
  if (odds === null) return '–'
  return odds > 0 ? `+${odds}` : `${odds}`
}

function fmtPct(p) {
  if (p === null) return '–'
  return (p * 100).toFixed(2) + '%'
}

function fmtDec(d) {
  if (d === null) return '–'
  return d.toFixed(3)
}

// ── Empirical margin distributions ───────────────────────────────────────────
// P(winning margin = exactly k points) from historical game results.
// NFL:  2,607 regular-season games, 2014–2023, via nfl_data_py
// NBA:  5,829 regular-season games, 2019-20–2023-24, via nba_api
// CFB:  2,218 FBS games, 2015–2023, via ESPN scoreboard API

const MARGIN_DIST = {
  // NFL: key numbers at 3 (14.4%) and 7 (8.5%) dominate
  NFL: {
    1:0.0433, 2:0.0449, 3:0.1438, 4:0.0464, 5:0.0403, 6:0.0671,
    7:0.0848, 8:0.0445, 9:0.0184, 10:0.0502, 11:0.0253, 12:0.0184,
    13:0.0196, 14:0.0556, 15:0.0176, 16:0.0257, 17:0.0318, 18:0.0219,
    19:0.0107, 20:0.0219, 21:0.0238, 22:0.0092, 23:0.0123, 24:0.0184,
    25:0.0100, 26:0.0107, 27:0.0092, 28:0.0153, 29:0.0054, 30:0.0046,
  },
  // NBA: no dominant key numbers — margins 4–9 cluster equally (~5.6–6.1%)
  NBA: {
    1:0.0403, 2:0.0494, 3:0.0558, 4:0.0559, 5:0.0570, 6:0.0612,
    7:0.0556, 8:0.0600, 9:0.0568, 10:0.0456, 11:0.0431, 12:0.0439,
    13:0.0345, 14:0.0357, 15:0.0335, 16:0.0273, 17:0.0221, 18:0.0232,
    19:0.0206, 20:0.0202, 21:0.0214, 22:0.0141, 23:0.0141, 24:0.0113,
    25:0.0120, 26:0.0084, 27:0.0089, 28:0.0077, 29:0.0087, 30:0.0079,
  },
  // CFB: key numbers at 3 (7.9%), 7 (7.8%), with TD-multiples 14/21/28 also elevated
  CFB: {
    1:0.0248, 2:0.0234, 3:0.0789, 4:0.0293, 5:0.0225, 6:0.0325,
    7:0.0780, 8:0.0225, 9:0.0144, 10:0.0406, 11:0.0248, 12:0.0081,
    13:0.0171, 14:0.0406, 15:0.0122, 16:0.0126, 17:0.0289, 18:0.0230,
    19:0.0113, 20:0.0158, 21:0.0374, 22:0.0131, 23:0.0144, 24:0.0266,
    25:0.0171, 26:0.0108, 27:0.0135, 28:0.0311, 29:0.0135, 30:0.0086,
  },
}

// ── Spread pricing model ──────────────────────────────────────────────────────
//
// Two concepts:
//
//   P_excess(S) = P(favorite wins by more than S)
//              = P(margin ≥ floor(S)+1)   [step function, jumps at integers]
//
//   P_win(S)    = effective bet-win probability accounting for pushes
//              = P_excess(S)              for half-point S  (no push possible)
//              = P_excess(S) / (1 - P(push))  for integer S  (push returns stake)
//
// MARGIN_DIST[k] is P(game decided by exactly k) from EITHER side.
// P(FAVORITE wins by exactly k) ≈ MARGIN_DIST[k] / 2  (near-even game assumption).
//
// Example: -3.5 and -3.0 have identical P_excess (both win on margin ≥ 4),
// but -3.0 has a push ~7.5% of the time, making it materially more valuable.

function fairProbAtSpread(s0, p0, s, dist) {
  if (s === s0) return p0

  // Work in threshold space: T = spread (positive = laying points, the natural input convention).
  // User enters 3.5 for "team lays 3.5"; display flips it to show "-3.5".
  // P(cover) = P(Team A margin > T), step function of T with dist[|k|]/2 at each integer k.
  const T0 = s0
  const T  = s

  const s0Int = s0 % 1 === 0
  const sInt  = s  % 1 === 0

  // 1. Recover P_excess = P(margin > T0) from anchor win probability.
  //    Integer spreads are push-adjusted: p0 = P_excess / (1 - P_push).
  const pushP0   = s0Int ? (dist[Math.abs(T0)] || 0) / 2 : 0
  const pExcess0 = s0Int ? p0 * (1 - pushP0) : p0

  // 2. Adjust P_excess along the T axis.
  //    P(margin > T) is a step function: each integer k crossed adds/subtracts dist[|k|]/2.
  //    Moving T down (easier spread): add P(margin = k) for each k crossed.
  //    Moving T up   (harder  spread): subtract P(margin = k) for each k crossed.
  let pExcess = pExcess0
  const loK = Math.floor(Math.min(T0, T)) + 1
  const hiK = Math.floor(Math.max(T0, T))
  const goingDown = T < T0
  for (let k = loK; k <= hiK; k++) {
    const probK = k !== 0 ? (dist[Math.abs(k)] || 0) / 2 : 0
    pExcess += goingDown ? probK : -probK
  }
  pExcess = Math.max(0.01, Math.min(0.99, pExcess))

  // 3. Convert P_excess → P_win for integer target spreads (push returns stake).
  if (sInt) {
    const pushP = (dist[Math.abs(T)] || 0) / 2
    return Math.max(0.01, Math.min(0.99, pExcess / (1 - pushP)))
  }
  return pExcess
}

// ── Shared UI ─────────────────────────────────────────────────────────────────

const TABS = ['Compare Lines', 'No-Vig', 'Parlay', 'Odds Converter', 'EV Calculator']

function OddsInput({ label, value, onChange, placeholder = 'ex. -110' }) {
  return (
    <div className="flex flex-col gap-1">
      {label && <label className="text-xs text-gray-400 uppercase tracking-wider font-sans">{label}</label>}
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-[#0d0d1a] border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm w-full focus:outline-none focus:border-blue-500 placeholder-gray-600"
      />
    </div>
  )
}

function StatBox({ label, value, highlight }) {
  return (
    <div className={`rounded p-3 text-center ${highlight ? 'bg-blue-900/40 border border-blue-500/40' : 'bg-[#0d0d1a] border border-gray-800'}`}>
      <div className="text-xs text-gray-400 uppercase tracking-wider font-sans mb-1">{label}</div>
      <div className={`font-mono text-lg font-bold ${highlight ? 'text-blue-300' : 'text-white'}`}>{value}</div>
    </div>
  )
}

function Card({ children, className = '' }) {
  return (
    <div className={`bg-[#141428] border border-gray-800 rounded-xl p-5 ${className}`}>
      {children}
    </div>
  )
}

function ResultTag({ better }) {
  if (better === null) return null
  return (
    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded ${
      better ? 'bg-green-900/50 text-green-400 border border-green-700' : 'bg-red-900/30 text-red-400 border border-red-800'
    }`}>
      {better ? '✓ BETTER LINE' : 'WORSE LINE'}
    </span>
  )
}

// ── Calculator 1: Compare Lines ───────────────────────────────────────────────

const SPORTS = ['NFL', 'NBA', 'CFB']

function CompareLines() {
  const [sport,    setSport]    = useState('NFL')
  const [l1spread, setL1spread] = useState('')
  const [l1price,  setL1price]  = useState('')
  const [l2spread, setL2spread] = useState('')
  const [l2price,  setL2price]  = useState('')

  const dist = MARGIN_DIST[sport]

  // Parse anchor (line 1)
  const s1 = parseFloat(l1spread)
  const o1 = parseOdds(l1price)
  const p1 = americanToProb(o1)   // anchor implied prob

  // Parse comparison (line 2)
  const s2 = parseFloat(l2spread)
  const o2 = parseOdds(l2price)
  const p2 = americanToProb(o2)   // actual implied prob at s2

  // Fair prob at s2 given anchor (s1, p1)
  const fairP2 = (p1 !== null && !isNaN(s1) && !isNaN(s2))
    ? fairProbAtSpread(s1, p1, s2, dist)
    : null

  // Edge: positive = line 2 is cheaper than fair (good for bettor)
  const edge = fairP2 !== null && p2 !== null
    ? (fairP2 - p2) * 100
    : null

  const l2Better = edge !== null && edge > 0.2
  const l1Better = edge !== null && edge < -0.2

  // Spread table: generate ±7 half-points around anchor
  const tableRows = (p1 !== null && !isNaN(s1))
    ? Array.from({ length: 29 }, (_, i) => {
        const sp = Math.round((s1 - 7 + i * 0.5) * 2) / 2
        const fair = fairProbAtSpread(s1, p1, sp, dist)
        const am = probToAmerican(fair)
        // half-point value vs previous row
        const prev = i > 0 ? fairProbAtSpread(s1, p1, sp - 0.5, dist) : null
        const delta = prev !== null ? (fair - prev) * 100 : null
        return { sp, fair, am, delta }
      })
    : []

  return (
    <div className="space-y-5">
      {/* Sport picker */}
      <div className="flex gap-2">
        {SPORTS.map((s) => (
          <button key={s} onClick={() => setSport(s)}
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
              sport === s ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}>{s}</button>
        ))}
      </div>

      {/* Line inputs */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <div className="font-medium text-snow text-base mb-3">
            Line 1 <span className="text-xs text-gray-400 font-sans tracking-normal ml-1">(anchor)</span>
          </div>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <OddsInput label="Spread" value={l1spread} onChange={setL1spread} placeholder="ex. 3.5" />
            <OddsInput label="Price"  value={l1price}  onChange={setL1price} />
          </div>
          {p1 !== null && (
            <div className="grid grid-cols-2 gap-2">
              <StatBox label="Implied Prob" value={fmtPct(p1)} />
              <StatBox label="Break-Even"   value={fmtPct(p1)} />
            </div>
          )}
        </Card>

        <Card>
          <div className="flex items-center justify-between mb-3">
            <div className="font-medium text-snow text-base">
              Line 2 <span className="text-xs text-gray-400 font-sans tracking-normal ml-1">(compare)</span>
            </div>
            {edge !== null && (
              <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
                l2Better ? 'bg-green-900/50 text-green-400 border-green-700' :
                l1Better ? 'bg-red-900/30 text-red-400 border-red-800' :
                'bg-gray-800 text-gray-400 border-gray-700'
              }`}>
                {l2Better ? '✓ BETTER VALUE' : l1Better ? 'WORSE VALUE' : 'EQUIVALENT'}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <OddsInput label="Spread" value={l2spread} onChange={setL2spread} placeholder="ex. 4.5" />
            <OddsInput label="Price"  value={l2price}  onChange={setL2price} />
          </div>
          {(p2 !== null || fairP2 !== null) && (
            <div className="grid grid-cols-2 gap-2">
              <StatBox label="Actual Implied" value={fmtPct(p2)} />
              <StatBox label={`Fair @ ${isNaN(s2) ? '–' : s2}`} value={fmtPct(fairP2)} highlight />
            </div>
          )}
        </Card>
      </div>

      {/* Edge summary */}
      {edge !== null && (
        <Card className="text-center">
          <div className="text-xs text-gray-400 uppercase tracking-wider mb-1 font-sans">
            Edge on Line 2 vs. fair value
          </div>
          <div className={`text-4xl font-mono font-bold mb-1 ${
            l2Better ? 'text-green-400' : l1Better ? 'text-red-400' : 'text-gray-300'
          }`}>
            {edge > 0 ? '+' : ''}{edge.toFixed(2)}%
          </div>
          <div className="text-sm text-gray-400 font-sans">
            {l2Better
              ? `Line 2 (${s2}) is priced ${edge.toFixed(2)}% cheaper than fair — take Line 2`
              : l1Better
              ? `Line 2 (${s2}) is overpriced by ${Math.abs(edge).toFixed(2)}% — stick with Line 1`
              : 'Lines are roughly equivalent after accounting for the spread difference'}
          </div>
          {fairP2 !== null && p2 !== null && (
            <div className="text-xs text-gray-500 font-sans mt-1">
              Fair price at {isNaN(s2) ? '–' : s2}: {fmtAmerican(probToAmerican(fairP2))}
              {' '}· Actual: {fmtAmerican(o2)}
            </div>
          )}
        </Card>
      )}

      {/* Spread pricing table */}
      {tableRows.length > 0 && (
        <Card>
          <div className="text-xs text-gray-400 uppercase tracking-wider mb-3 font-sans">
            Fair Prices — All Spreads ({sport} empirical data, anchored at {s1} = {fmtAmerican(o1)})
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm font-sans">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left py-1.5 px-2 text-xs text-gray-500 uppercase">Spread</th>
                  <th className="text-right py-1.5 px-2 text-xs text-gray-500 uppercase">Fair Price</th>
                  <th className="text-right py-1.5 px-2 text-xs text-gray-500 uppercase">Implied %</th>
                  <th className="text-right py-1.5 px-2 text-xs text-gray-500 uppercase">Δ Prob</th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map(({ sp, fair, am, delta }) => {
                  const isAnchor = sp === s1
                  const isLine2  = !isNaN(s2) && sp === s2
                  // highlight key numbers: large delta means we're crossing a key margin
                  const isKey = delta !== null && Math.abs(delta) >= 5
                  return (
                    <tr key={sp} className={`border-b border-gray-800/50 ${
                      isAnchor ? 'bg-blue-900/30' : isLine2 ? 'bg-yellow-900/20' : ''
                    }`}>
                      <td className="py-1.5 px-2 font-mono">
                        <span className={isAnchor ? 'text-blue-300 font-bold' : isLine2 ? 'text-yellow-300 font-bold' : 'text-gray-300'}>
                          {sp > 0 ? '-' : '+'}{Math.abs(sp)}
                        </span>
                        {isAnchor && <span className="ml-1.5 text-xs text-blue-500">anchor</span>}
                        {isLine2  && <span className="ml-1.5 text-xs text-yellow-500">line 2</span>}
                      </td>
                      <td className="py-1.5 px-2 text-right font-mono text-gray-200">
                        {fmtAmerican(am)}
                      </td>
                      <td className="py-1.5 px-2 text-right font-mono text-gray-400">
                        {(fair * 100).toFixed(1)}%
                      </td>
                      <td className={`py-1.5 px-2 text-right font-mono text-xs ${
                        isKey ? 'text-yellow-400 font-bold' : 'text-gray-600'
                      }`}>
                        {delta !== null ? (delta > 0 ? '+' : '') + delta.toFixed(1) + '%' : '–'}
                        {isKey && ' ★'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-600 font-sans mt-2">
            ★ marks half-points crossing key numbers (large probability jumps). Spread shown as favorite laying points.
          </p>
        </Card>
      )}
    </div>
  )
}

// ── Calculator 2: No-Vig ──────────────────────────────────────────────────────

function NoVig() {
  const [side1, setSide1] = useState('')
  const [side2, setSide2] = useState('')

  const o1 = parseOdds(side1)
  const o2 = parseOdds(side2)
  const p1 = americanToProb(o1)
  const p2 = americanToProb(o2)

  const total = p1 !== null && p2 !== null ? p1 + p2 : null
  const vig   = total !== null ? (total - 1) * 100 : null
  const fair1 = total !== null ? p1 / total : null
  const fair2 = total !== null ? p2 / total : null

  return (
    <div className="space-y-4">
      <Card>
        <div className="text-sm text-gray-400 font-sans mb-4">
          Enter both sides of a market to remove the sportsbook's margin and find the true (no-vig) odds.
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <OddsInput label="Side A (e.g. favorite)" value={side1} onChange={setSide1} placeholder="ex. -115" />
          <OddsInput label="Side B (e.g. underdog)"  value={side2} onChange={setSide2} placeholder="ex. +105" />
        </div>
      </Card>

      {total !== null && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <StatBox label="Vig (Juice)" value={vig !== null ? vig.toFixed(2) + '%' : '–'} />
            <StatBox label="Market Total" value={total !== null ? fmtPct(total) : '–'} />
            <StatBox label="Book Margin" value={vig !== null ? '$' + (vig * 0.91).toFixed(2) + ' / $100' : '–'} />
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <Card>
              <div className="font-medium text-snow mb-3">Side A — Fair Odds</div>
              <div className="grid grid-cols-2 gap-2">
                <StatBox label="Fair Prob"    value={fmtPct(fair1)} highlight />
                <StatBox label="Fair American" value={fmtAmerican(probToAmerican(fair1))} highlight />
              </div>
              <div className="grid grid-cols-2 gap-2 mt-2">
                <StatBox label="Fair Decimal" value={fair1 !== null ? fmtDec(1 / fair1) : '–'} />
                <StatBox label="Implied Prob" value={fmtPct(p1)} />
              </div>
            </Card>
            <Card>
              <div className="font-medium text-snow mb-3">Side B — Fair Odds</div>
              <div className="grid grid-cols-2 gap-2">
                <StatBox label="Fair Prob"    value={fmtPct(fair2)} highlight />
                <StatBox label="Fair American" value={fmtAmerican(probToAmerican(fair2))} highlight />
              </div>
              <div className="grid grid-cols-2 gap-2 mt-2">
                <StatBox label="Fair Decimal" value={fair2 !== null ? fmtDec(1 / fair2) : '–'} />
                <StatBox label="Implied Prob" value={fmtPct(p2)} />
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

// ── Calculator 3: Parlay ──────────────────────────────────────────────────────

function Parlay() {
  const [legs, setLegs] = useState(['', '', ''])
  const [wager, setWager] = useState('100')

  const addLeg    = () => setLegs((l) => [...l, ''])
  const removeLeg = (i) => setLegs((l) => l.filter((_, j) => j !== i))
  const setLeg    = (i, v) => setLegs((l) => l.map((x, j) => j === i ? v : x))

  const decimals = legs.map((l) => {
    const o = parseOdds(l)
    if (o === null) return null
    // handle decimal input directly (>= 1.01 and no +/-)
    if (!String(l).trim().startsWith('+') && !String(l).trim().startsWith('-') && parseFloat(l) < 100 && parseFloat(l) > 1) {
      return parseFloat(l)
    }
    return americanToDecimal(o)
  })

  const validDecimals = decimals.filter(Boolean)
  const combinedDecimal = validDecimals.length > 1
    ? validDecimals.reduce((acc, d) => acc * d, 1)
    : null

  const combinedAmerican = combinedDecimal !== null ? decimalToAmerican(combinedDecimal) : null
  const w = parseFloat(wager) || 0
  const payout  = combinedDecimal !== null ? combinedDecimal * w : null
  const profit  = payout !== null ? payout - w : null

  return (
    <div className="space-y-4">
      <Card>
        <div className="text-sm text-gray-400 font-sans mb-4">
          Enter each leg's odds. Supports American (−110), decimal (1.91), or mixed.
        </div>

        <div className="space-y-2 mb-4">
          {legs.map((leg, i) => (
            <div key={i} className="flex gap-2 items-end">
              <div className="flex-1">
                <OddsInput
                  label={i === 0 ? 'Leg Odds' : undefined}
                  value={leg}
                  onChange={(v) => setLeg(i, v)}
                  placeholder={`Leg ${i + 1}, ex. -110`}
                />
              </div>
              {legs.length > 2 && (
                <button
                  onClick={() => removeLeg(i)}
                  className="text-gray-600 hover:text-red-400 text-lg pb-1.5 transition-colors"
                >
                  ×
                </button>
              )}
            </div>
          ))}
        </div>

        <button
          onClick={addLeg}
          disabled={legs.length >= 12}
          className="text-xs text-blue-400 hover:text-blue-300 font-sans transition-colors disabled:opacity-40"
        >
          + Add leg
        </button>
      </Card>

      <Card>
        <div className="text-xs text-gray-400 uppercase tracking-wider font-sans mb-2">Wager</div>
        <div className="flex gap-2 items-center mb-4">
          <span className="text-gray-400 font-mono">$</span>
          <input
            type="number"
            value={wager}
            onChange={(e) => setWager(e.target.value)}
            className="bg-[#0d0d1a] border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm w-32 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatBox label="Legs" value={validDecimals.length} />
          <StatBox label="Combined Odds" value={fmtAmerican(combinedAmerican)} highlight />
          <StatBox label="Payout" value={payout !== null ? '$' + payout.toFixed(2) : '–'} highlight />
          <StatBox label="Profit" value={profit !== null ? '$' + profit.toFixed(2) : '–'} />
        </div>

        {combinedDecimal !== null && (
          <div className="mt-3 grid grid-cols-2 gap-3">
            <StatBox label="Combined Decimal" value={fmtDec(combinedDecimal)} />
            <StatBox label="Implied Prob to Win" value={fmtPct(1 / combinedDecimal)} />
          </div>
        )}
      </Card>
    </div>
  )
}

// ── Calculator 4: Odds Converter ─────────────────────────────────────────────

function OddsConverter() {
  const [american,  setAmerican]  = useState('')
  const [decimal,   setDecimal]   = useState('')
  const [fracNum,   setFracNum]   = useState('')
  const [fracDen,   setFracDen]   = useState('')
  const [impliedPct, setImplied]  = useState('')
  const [source,    setSource]    = useState(null)  // which field was last edited

  function fromAmerican(raw) {
    const o = parseOdds(raw)
    if (o === null) return
    setSource('american')
    const dec = americanToDecimal(o)
    const prob = americanToProb(o)
    setDecimal(dec !== null ? dec.toFixed(4) : '')
    if (dec !== null) {
      const n = dec - 1, d = 1
      const g = gcd(Math.round(n * 100), 100)
      setFracNum(String(Math.round(n * 100 / g)))
      setFracDen(String(100 / g))
    }
    setImplied(prob !== null ? (prob * 100).toFixed(2) : '')
  }

  function fromDecimal(raw) {
    const d = parseFloat(raw)
    if (isNaN(d) || d <= 1) return
    setSource('decimal')
    const am = decimalToAmerican(d)
    const prob = 1 / d
    setAmerican(am !== null ? fmtAmerican(am) : '')
    const n = d - 1
    const g = gcd(Math.round(n * 100), 100)
    setFracNum(String(Math.round(n * 100 / g)))
    setFracDen(String(100 / g))
    setImplied((prob * 100).toFixed(2))
  }

  function fromFraction() {
    const n = parseFloat(fracNum), d = parseFloat(fracDen)
    if (isNaN(n) || isNaN(d) || d === 0) return
    setSource('fraction')
    const dec = n / d + 1
    const prob = 1 / dec
    const am = decimalToAmerican(dec)
    setDecimal(dec.toFixed(4))
    setAmerican(am !== null ? fmtAmerican(am) : '')
    setImplied((prob * 100).toFixed(2))
  }

  function fromImplied(raw) {
    const p = parseFloat(raw) / 100
    if (isNaN(p) || p <= 0 || p >= 1) return
    setSource('implied')
    const dec = 1 / p
    const am = decimalToAmerican(dec)
    setDecimal(dec.toFixed(4))
    setAmerican(am !== null ? fmtAmerican(am) : '')
    const n = dec - 1
    const g = gcd(Math.round(n * 100), 100)
    setFracNum(String(Math.round(n * 100 / g)))
    setFracDen(String(100 / g))
  }

  return (
    <div className="space-y-4 max-w-lg">
      <Card>
        <div className="text-sm text-gray-400 font-sans mb-4">
          Enter odds in any format — all others update automatically.
        </div>
        <div className="space-y-3">
          <OddsInput
            label="American"
            value={american}
            onChange={(v) => { setAmerican(v); fromAmerican(v) }}
            placeholder="ex. -110 or +150"
          />
          <OddsInput
            label="Decimal"
            value={decimal}
            onChange={(v) => { setDecimal(v); fromDecimal(v) }}
            placeholder="ex. 1.909"
          />
          <div>
            <label className="text-xs text-gray-400 uppercase tracking-wider font-sans">Fractional</label>
            <div className="flex items-center gap-2 mt-1">
              <input
                type="text" value={fracNum}
                onChange={(e) => { setFracNum(e.target.value); fromFraction() }}
                placeholder="10"
                className="bg-[#0d0d1a] border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm w-24 focus:outline-none focus:border-blue-500"
              />
              <span className="text-gray-400 font-mono text-lg">/</span>
              <input
                type="text" value={fracDen}
                onChange={(e) => { setFracDen(e.target.value); fromFraction() }}
                placeholder="11"
                className="bg-[#0d0d1a] border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm w-24 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 uppercase tracking-wider font-sans">Implied Probability (%)</label>
            <div className="flex items-center gap-2 mt-1">
              <input
                type="text" value={impliedPct}
                onChange={(e) => { setImplied(e.target.value); fromImplied(e.target.value) }}
                placeholder="52.38"
                className="bg-[#0d0d1a] border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm w-32 focus:outline-none focus:border-blue-500"
              />
              <span className="text-gray-400 font-mono">%</span>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}

function gcd(a, b) { return b === 0 ? a : gcd(b, a % b) }

// ── Calculator 5: EV Calculator ───────────────────────────────────────────────

function EVCalc() {
  const [marketOdds, setMarketOdds] = useState('')
  const [winPct,     setWinPct]     = useState('')
  const [wager,      setWager]      = useState('100')

  const o   = parseOdds(marketOdds)
  const dec = americanToDecimal(o)
  const w   = parseFloat(wager) || 0
  const p   = parseFloat(winPct) / 100

  const impliedProb = americanToProb(o)

  const ev = dec !== null && !isNaN(p) && p > 0 && p < 1
    ? (p * (dec - 1) * w) - ((1 - p) * w)
    : null

  const edge = impliedProb !== null && !isNaN(p)
    ? (p - impliedProb) * 100
    : null

  const roi = ev !== null ? (ev / w) * 100 : null
  const positive = ev !== null && ev > 0

  return (
    <div className="space-y-4 max-w-lg">
      <Card>
        <div className="text-sm text-gray-400 font-sans mb-4">
          Enter the market odds and your estimated true win probability to calculate expected value.
        </div>
        <div className="space-y-3">
          <OddsInput
            label="Market Odds"
            value={marketOdds}
            onChange={setMarketOdds}
            placeholder="ex. -110"
          />
          <div>
            <label className="text-xs text-gray-400 uppercase tracking-wider font-sans">Your Win Estimate (%)</label>
            <div className="flex items-center gap-2 mt-1">
              <input
                type="text"
                value={winPct}
                onChange={(e) => setWinPct(e.target.value)}
                placeholder="55"
                className="bg-[#0d0d1a] border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm w-32 focus:outline-none focus:border-blue-500"
              />
              <span className="text-gray-400 font-mono">%</span>
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 uppercase tracking-wider font-sans">Wager</label>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-gray-400 font-mono">$</span>
              <input
                type="number"
                value={wager}
                onChange={(e) => setWager(e.target.value)}
                className="bg-[#0d0d1a] border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm w-32 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
        </div>
      </Card>

      {ev !== null && (
        <>
          <div className={`rounded-xl border p-4 text-center ${positive ? 'bg-green-950 border-green-700' : 'bg-red-950 border-red-800'}`}>
            <div className="text-xs text-gray-400 uppercase tracking-wider font-sans mb-1">Expected Value per ${w.toFixed(0)} wager</div>
            <div className={`text-4xl font-mono font-bold ${positive ? 'text-green-400' : 'text-red-400'}`}>
              {positive ? '+' : ''}{ev.toFixed(2)}
            </div>
            <div className="text-sm text-gray-400 font-sans mt-1">
              {positive ? 'Positive EV — this bet has an edge' : 'Negative EV — you are the underdog here'}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <StatBox label="Edge" value={edge !== null ? (edge > 0 ? '+' : '') + edge.toFixed(2) + '%' : '–'} highlight={positive} />
            <StatBox label="ROI" value={roi !== null ? (roi > 0 ? '+' : '') + roi.toFixed(2) + '%' : '–'} />
            <StatBox label="Break-Even" value={fmtPct(impliedProb)} />
          </div>

          <Card>
            <div className="text-xs text-gray-400 uppercase tracking-wider font-sans mb-2">Kelly Criterion</div>
            {(() => {
              if (!impliedProb || !p || dec === null) return null
              const q = 1 - p
              const b = dec - 1
              const kelly = (p * b - q) / b
              const halfKelly = kelly / 2
              return (
                <div className="grid grid-cols-2 gap-3">
                  <StatBox label="Full Kelly %" value={kelly > 0 ? (kelly * 100).toFixed(2) + '%' : 'No bet'} />
                  <StatBox label="Half Kelly %" value={halfKelly > 0 ? (halfKelly * 100).toFixed(2) + '%' : 'No bet'} />
                </div>
              )
            })()}
            <p className="text-xs text-gray-600 font-sans mt-2">
              Kelly = fraction of bankroll to wager for maximum growth rate. Most pros use ¼–½ Kelly.
            </p>
          </Card>
        </>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Betting() {
  const [tab, setTab] = useState(0)

  return (
    <div className="min-h-screen bg-void">
      <Navbar />

      {/* Header */}
      <header className="px-6 py-7" style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 mb-1.5">
            <span
              className="text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
              style={{ background: 'rgba(16,185,129,0.12)', color: '#10B981', border: '1px solid rgba(16,185,129,0.2)' }}
            >
              Calculators
            </span>
            <h1 className="text-snow font-bold text-2xl tracking-tight" style={{ letterSpacing: '-0.02em' }}>
              Betting Tools
            </h1>
          </div>
          <p className="text-mist text-sm leading-relaxed">
            Compare lines, remove vig, build parlays, convert odds, and calculate expected value.
          </p>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Tab bar */}
        <div className="flex flex-wrap mb-6 gap-1">
          {TABS.map((t, i) => (
            <button
              key={t}
              onClick={() => setTab(i)}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap"
              style={{
                background: tab === i ? 'rgba(16,185,129,0.15)' : 'transparent',
                color: tab === i ? '#10B981' : '#86868B',
                border: tab === i ? '1px solid rgba(16,185,129,0.3)' : '1px solid transparent',
              }}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === 0 && <CompareLines />}
        {tab === 1 && <NoVig />}
        {tab === 2 && <Parlay />}
        {tab === 3 && <OddsConverter />}
        {tab === 4 && <EVCalc />}
      </div>
    </div>
  )
}

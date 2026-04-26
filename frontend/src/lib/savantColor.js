/**
 * Baseball Savant-style diverging colormap.
 *
 * Maps a percentile 0..1 to a background/foreground color pair.
 *   0.00  → deep blue    (worst)
 *   0.50  → white        (median)
 *   1.00  → deep red     (best)
 *
 * If `higherIsBetter` is false, the scale is inverted.
 *
 * Returns a style object `{ backgroundColor, color }` suitable for inline
 * styling of `<td>` cells. In light mode, the text color is white near the
 * extremes and dark near the middle, matching Savant.
 */
const BLUE_DEEP = [42,  99,  182]   // #2A63B6
const BLUE_MID  = [139, 178, 216]   // #8BB2D8
const WHITE     = [245, 245, 247]   // #F5F5F7 (Apple off-white, blends with page)
const RED_MID   = [237, 136, 123]   // #ED887B
const RED_DEEP  = [196,  46,  58]   // #C42E3A

function lerp(a, b, t) { return a + (b - a) * t }
function lerpColor(c1, c2, t) {
  return [lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t)]
}
function rgb([r, g, b]) {
  return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`
}

export function savantColor(pct, higherIsBetter = true) {
  if (pct == null || isNaN(pct)) return { backgroundColor: 'transparent', color: '#1D1D1F' }
  const p = higherIsBetter ? pct : 1 - pct
  const clamped = Math.max(0, Math.min(1, p))

  // 5-stop gradient
  let rgbArr
  if (clamped <= 0.25) {
    rgbArr = lerpColor(BLUE_DEEP, BLUE_MID, clamped / 0.25)
  } else if (clamped <= 0.50) {
    rgbArr = lerpColor(BLUE_MID, WHITE, (clamped - 0.25) / 0.25)
  } else if (clamped <= 0.75) {
    rgbArr = lerpColor(WHITE, RED_MID, (clamped - 0.50) / 0.25)
  } else {
    rgbArr = lerpColor(RED_MID, RED_DEEP, (clamped - 0.75) / 0.25)
  }

  // Text color: white near the extremes (where bg is saturated), dark near center
  const textColor = (clamped < 0.18 || clamped > 0.82) ? '#FFFFFF' : '#1D1D1F'

  return {
    backgroundColor: rgb(rgbArr),
    color: textColor,
  }
}

/**
 * Linear percentile ranking — for a given value, find its percentile within
 * the sorted array of all values.
 */
export function percentileRank(value, sortedValues) {
  if (value == null || !sortedValues.length) return null
  let lo = 0, hi = sortedValues.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (sortedValues[mid] < value) lo = mid + 1
    else hi = mid
  }
  return lo / (sortedValues.length - 1 || 1)
}

/**
 * Map a raw stat (0..100 Stuff+ scale) to percentile-ish shading.
 * Stuff+ = 100 is league average → 0.5 on scale. 120 → 0.85, 80 → 0.15.
 */
export function stuffPlusPct(val) {
  if (val == null) return null
  // 80 Stuff+ → 0.0, 100 → 0.5, 120 → 1.0 (clamped)
  return Math.max(0, Math.min(1, (val - 80) / 40))
}

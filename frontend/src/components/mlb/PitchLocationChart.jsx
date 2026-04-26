import { pitchColor, PITCH_LABEL } from '../../lib/pitchColors'

// Converts real-world feet to SVG pixels
// plate_x: -1.5 → 1.5 ft  |  plate_z: 0 → 5.5 ft
const W = 280
const H = 300
const PAD = 20

const scaleX = (x) => PAD + ((x + 1.5) / 3) * (W - PAD * 2)
const scaleZ = (z) => H - PAD - ((z / 5.5) * (H - PAD * 2))

// Strike zone (approximate)
const SZ_X_L = scaleX(-0.8308)
const SZ_X_R = scaleX(0.8308)

export default function PitchLocationChart({ pitches = [], height = 300, title = 'Pitch Location' }) {
  // Derive SZ bounds from data median or use defaults
  const szTops = pitches.map((p) => p.sz_top).filter(Boolean)
  const szBots = pitches.map((p) => p.sz_bot).filter(Boolean)
  const medianSzTop = szTops.length ? median(szTops) : 3.5
  const medianSzBot = szBots.length ? median(szBots) : 1.5

  const szTop = scaleZ(medianSzTop)
  const szBot = scaleZ(medianSzBot)

  const activePitchTypes = [...new Set(pitches.map((p) => p.pitch_type).filter(Boolean))]

  return (
    <div
      className="rounded-xl p-3"
      style={{
        background: '#FFFFFF',
        border: '1px solid rgba(0,0,0,0.08)',
      }}
    >
      {title && (
        <div
          className="text-xs tracking-wider uppercase font-semibold mb-2"
          style={{ color: '#1D1D1F' }}
        >
          {title}
        </div>
      )}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        style={{ maxHeight: height, userSelect: 'none' }}
      >
        {/* Background */}
        <rect x={PAD} y={PAD} width={W - PAD * 2} height={H - PAD * 2}
              fill="#F5F5F7" stroke="rgba(0,0,0,0.08)" strokeWidth="1" strokeDasharray="4,4" />

        {/* Strike zone */}
        <rect
          x={SZ_X_L} y={szTop}
          width={SZ_X_R - SZ_X_L} height={szBot - szTop}
          fill="none" stroke="#1D1D1F" strokeWidth="2"
        />
        {/* Zone thirds — vertical */}
        {[-0.277, 0.277].map((x) => (
          <line key={x}
            x1={scaleX(x)} y1={szTop}
            x2={scaleX(x)} y2={szBot}
            stroke="rgba(0,0,0,0.25)" strokeWidth="1"
          />
        ))}
        {/* Zone thirds — horizontal */}
        {[medianSzBot + (medianSzTop - medianSzBot) / 3, medianSzBot + (2 * (medianSzTop - medianSzBot)) / 3].map((z) => (
          <line key={z}
            x1={SZ_X_L} y1={scaleZ(z)}
            x2={SZ_X_R} y2={scaleZ(z)}
            stroke="rgba(0,0,0,0.25)" strokeWidth="1"
          />
        ))}

        {/* Home plate shape */}
        <polygon
          points={`
            ${scaleX(-0.708)},${scaleZ(0.2)}
            ${scaleX(0.708)},${scaleZ(0.2)}
            ${scaleX(0.708)},${scaleZ(0.05)}
            ${scaleX(0)},${scaleZ(-0.1)}
            ${scaleX(-0.708)},${scaleZ(0.05)}
          `}
          fill="#E8E8ED" stroke="#86868B" strokeWidth="1"
        />

        {/* Center crosshair */}
        <line x1={scaleX(0)} y1={szTop - 8} x2={scaleX(0)} y2={szBot + 8}
              stroke="rgba(0,0,0,0.12)" strokeWidth="1" strokeDasharray="3,3" />

        {/* Pitches */}
        {pitches.map((p, i) => {
          if (p.plate_x == null || p.plate_z == null) return null
          return (
            <circle
              key={i}
              cx={scaleX(p.plate_x)}
              cy={scaleZ(p.plate_z)}
              r={5}
              fill={pitchColor(p.pitch_type)}
              fillOpacity={0.78}
              stroke="rgba(0,0,0,0.15)"
              strokeWidth={0.5}
            />
          )
        })}
      </svg>

      {/* Legend */}
      {activePitchTypes.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {activePitchTypes.map((pt) => (
            <div key={pt} className="flex items-center gap-1">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: pitchColor(pt), border: '1px solid rgba(0,0,0,0.15)' }}
              />
              <span className="text-xs" style={{ color: '#86868B' }}>
                {PITCH_LABEL[pt] || pt}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function median(arr) {
  const sorted = [...arr].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

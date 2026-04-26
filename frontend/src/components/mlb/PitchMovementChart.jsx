import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts'
import { pitchColor, PITCH_LABEL } from '../../lib/pitchColors'

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  return (
    <div
      className="text-xs p-2 rounded-lg shadow-lg"
      style={{
        background: '#FFFFFF',
        border: '1px solid rgba(0,0,0,0.10)',
        color: '#1D1D1F',
      }}
    >
      <div className="font-semibold mb-1">{PITCH_LABEL[d.pitch_type] || d.pitch_type}</div>
      <div>HB: {d.pfx_x != null ? (d.pfx_x * 12).toFixed(1) : '–'}"</div>
      <div>IVB: {d.pfx_z != null ? (d.pfx_z * 12).toFixed(1) : '–'}"</div>
      {d.release_speed && <div>Velo: {d.release_speed.toFixed(1)} mph</div>}
      {d.release_spin_rate && <div>Spin: {Math.round(d.release_spin_rate)} rpm</div>}
    </div>
  )
}

export default function PitchMovementChart({ pitches = [], title = 'Movement Profile' }) {
  // Convert feet → inches for display
  const data = pitches
    .filter((p) => p.pfx_x != null && p.pfx_z != null)
    .map((p) => ({
      ...p,
      hb: parseFloat((p.pfx_x * 12).toFixed(2)),   // horizontal break in inches
      ivb: parseFloat((p.pfx_z * 12).toFixed(2)),  // induced vertical break
    }))

  const activePitchTypes = [...new Set(data.map((p) => p.pitch_type).filter(Boolean))]

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
          className="text-xs tracking-wider uppercase font-semibold mb-3"
          style={{ color: '#1D1D1F' }}
        >
          {title}
        </div>
      )}
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.08)" />
          <XAxis
            dataKey="hb"
            type="number"
            domain={[-25, 25]}
            label={{ value: 'Horizontal Break (in)', position: 'bottom', fill: '#86868B', fontSize: 11 }}
            tick={{ fill: '#86868B', fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(0,0,0,0.15)' }}
          />
          <YAxis
            dataKey="ivb"
            type="number"
            domain={[-25, 25]}
            label={{ value: 'IVB (in)', angle: -90, position: 'left', fill: '#86868B', fontSize: 11 }}
            tick={{ fill: '#86868B', fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(0,0,0,0.15)' }}
          />
          <ReferenceLine x={0} stroke="rgba(0,0,0,0.25)" strokeWidth={1} />
          <ReferenceLine y={0} stroke="rgba(0,0,0,0.25)" strokeWidth={1} />
          <Tooltip content={<CustomTooltip />} />
          <Scatter data={data} isAnimationActive={false}>
            {data.map((entry, i) => (
              <Cell key={i} fill={pitchColor(entry.pitch_type)} fillOpacity={0.75} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>

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

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
    <div className="bg-sv-dark border border-gray-600 text-white text-xs p-2 rounded shadow-lg">
      <div className="font-bold mb-1">{PITCH_LABEL[d.pitch_type] || d.pitch_type}</div>
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
    <div className="bg-sv-dark rounded p-3">
      <div className="text-white text-xs font-bangers tracking-wider mb-3">{title}</div>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis
            dataKey="hb"
            type="number"
            domain={[-25, 25]}
            label={{ value: 'Horizontal Break (in)', position: 'bottom', fill: '#aaa', fontSize: 11 }}
            tick={{ fill: '#aaa', fontSize: 10 }}
            tickLine={false}
          />
          <YAxis
            dataKey="ivb"
            type="number"
            domain={[-25, 25]}
            label={{ value: 'IVB (in)', angle: -90, position: 'left', fill: '#aaa', fontSize: 11 }}
            tick={{ fill: '#aaa', fontSize: 10 }}
            tickLine={false}
          />
          <ReferenceLine x={0} stroke="#555" strokeWidth={1} />
          <ReferenceLine y={0} stroke="#555" strokeWidth={1} />
          <Tooltip content={<CustomTooltip />} />
          <Scatter data={data} isAnimationActive={false}>
            {data.map((entry, i) => (
              <Cell key={i} fill={pitchColor(entry.pitch_type)} fillOpacity={0.7} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>

      {activePitchTypes.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {activePitchTypes.map((pt) => (
            <div key={pt} className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full border border-black/20"
                   style={{ backgroundColor: pitchColor(pt) }} />
              <span className="text-xs text-gray-300">{PITCH_LABEL[pt] || pt}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

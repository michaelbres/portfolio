import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, LineChart, Line, Legend,
} from 'recharts'
import Navbar from '../../../components/Navbar'
import PitchLocationChart from '../../../components/mlb/PitchLocationChart'
import PitchMovementChart from '../../../components/mlb/PitchMovementChart'
import LeaderboardTable from '../../../components/mlb/LeaderboardTable'
import { mlb } from '../../../lib/api'
import { pitchColor, PITCH_LABEL } from '../../../lib/pitchColors'

const TABS = ['Arsenal', 'Location', 'Movement', 'Pitch Log']

const PITCH_LOG_COLS = [
  { key: 'game_date',     label: 'Date' },
  { key: 'pitch_name',    label: 'Pitch' },
  { key: 'release_speed', label: 'Velo',  format: (v) => v?.toFixed(1) },
  { key: 'release_spin_rate', label: 'Spin', format: (v) => v ? Math.round(v) : '–' },
  { key: 'pfx_x',         label: 'HB"',   format: (v) => v != null ? (v * 12).toFixed(1) : '–' },
  { key: 'pfx_z',         label: 'IVB"',  format: (v) => v != null ? (v * 12).toFixed(1) : '–' },
  { key: 'plate_x',       label: 'pX',    format: (v) => v?.toFixed(2) },
  { key: 'plate_z',       label: 'pZ',    format: (v) => v?.toFixed(2) },
  { key: 'balls',         label: 'B' },
  { key: 'strikes',       label: 'S' },
  { key: 'description',   label: 'Result' },
  { key: 'events',        label: 'Event' },
  { key: 'launch_speed',  label: 'EV',    format: (v) => v?.toFixed(1) },
  { key: 'launch_angle',  label: 'LA',    format: (v) => v?.toFixed(1) },
  { key: 'estimated_woba_using_speedangle', label: 'xwOBA', format: (v) => v?.toFixed(3) },
]

export default function PitcherDetail() {
  const { id } = useParams()
  const [tab, setTab] = useState(0)
  const [summary, setSummary] = useState(null)
  const [pitches, setPitches] = useState([])
  const [loading, setLoading] = useState(true)
  const [season, setSeason] = useState(2025)
  const [selectedPitchType, setSelectedPitchType] = useState('')
  const [logOffset, setLogOffset] = useState(0)
  const [logTotal, setLogTotal] = useState(0)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      mlb.pitcherSummary(id, { season }),
      mlb.pitcherPitches(id, { season, limit: 2000 }),
    ])
      .then(([sumRes, pitchRes]) => {
        setSummary(sumRes.data)
        setPitches(pitchRes.data.data)
        setLogTotal(pitchRes.data.total)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [id, season])

  const filteredPitches = selectedPitchType
    ? pitches.filter((p) => p.pitch_type === selectedPitchType)
    : pitches

  if (loading) {
    return (
      <div className="min-h-screen bg-sv-light">
        <Navbar />
        <div className="flex items-center justify-center h-64 text-gray-400 font-sans animate-pulse">
          Loading pitcher data…
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="min-h-screen bg-sv-light">
        <Navbar />
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <div className="text-gray-600 font-sans">Pitcher not found.</div>
          <Link to="/sports/mlb" className="text-sv-blue hover:underline font-sans text-sm">
            ← Back to MLB
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-sv-light">
      <Navbar />

      {/* Header */}
      <header className="bg-sv-dark border-b-4 border-sv-red px-6 py-5">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center gap-2 text-xs text-gray-400 mb-3 font-sans">
            <Link to="/sports/mlb" className="hover:text-pop-yellow transition-colors">MLB</Link>
            <span>›</span>
            <span className="text-white">{summary.pitcher_name}</span>
          </div>
          <div className="flex flex-wrap items-end gap-6">
            <div>
              <h1 className="font-bangers text-white text-5xl tracking-wider leading-none">
                {summary.pitcher_name}
              </h1>
              <div className="flex items-center gap-3 mt-2">
                <span className="bg-sv-red text-white text-xs font-bangers px-2 py-0.5 tracking-wider">
                  {summary.p_throws === 'R' ? 'RHP' : summary.p_throws === 'L' ? 'LHP' : '–'}
                </span>
                <span className="text-gray-400 text-sm font-sans">
                  {summary.total_pitches?.toLocaleString()} pitches in {season}
                </span>
              </div>
            </div>
            <div className="ml-auto">
              <select
                value={season}
                onChange={(e) => setSeason(Number(e.target.value))}
                className="bg-sv-dark border border-gray-600 text-white px-3 py-1.5 rounded text-sm font-sans"
              >
                <option value={2025}>2025</option>
                <option value={2026}>2026</option>
              </select>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Tabs */}
        <div className="flex border-b-2 border-gray-300 mb-6">
          {TABS.map((t, i) => (
            <button
              key={t}
              onClick={() => setTab(i)}
              className={`px-5 py-3 font-bangers tracking-wider text-sm uppercase transition-colors border-b-4 -mb-0.5 ${
                tab === i
                  ? 'border-sv-red text-sv-red bg-white'
                  : 'border-transparent text-gray-500 hover:text-gray-800'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Pitch type filter pills */}
        {(tab === 1 || tab === 2) && (
          <div className="flex flex-wrap gap-2 mb-4">
            <PitchPill
              active={selectedPitchType === ''}
              onClick={() => setSelectedPitchType('')}
              label="All"
              color="#555"
            />
            {summary.arsenal.map((a) => (
              <PitchPill
                key={a.pitch_type}
                active={selectedPitchType === a.pitch_type}
                onClick={() => setSelectedPitchType(a.pitch_type)}
                label={`${a.pitch_name || a.pitch_type} (${a.usage_pct}%)`}
                color={pitchColor(a.pitch_type)}
              />
            ))}
          </div>
        )}

        {/* ── ARSENAL TAB ── */}
        {tab === 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Usage bar chart */}
            <div className="bg-white border border-gray-200 rounded shadow-sm p-4">
              <h3 className="font-bangers text-xl tracking-wider text-sv-dark mb-4">PITCH USAGE</h3>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart
                  data={[...summary.arsenal].sort((a, b) => b.count - a.count)}
                  margin={{ left: 10, right: 10, bottom: 30 }}
                  layout="vertical"
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tickFormatter={(v) => v + '%'} domain={[0, 'auto']}
                         tick={{ fontSize: 11 }} />
                  <YAxis
                    type="category" dataKey="pitch_name" width={120}
                    tick={{ fontSize: 11 }} tickLine={false}
                  />
                  <Tooltip formatter={(v) => v.toFixed(1) + '%'} />
                  <Bar dataKey="usage_pct" isAnimationActive={false}>
                    {summary.arsenal.map((a) => (
                      <Cell key={a.pitch_type} fill={pitchColor(a.pitch_type)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Arsenal stats table */}
            <div className="bg-white border border-gray-200 rounded shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200">
                <h3 className="font-bangers text-xl tracking-wider text-sv-dark">ARSENAL BREAKDOWN</h3>
              </div>
              <table className="savant-table">
                <thead>
                  <tr>
                    <th>Pitch</th>
                    <th>Usage</th>
                    <th>Velo</th>
                    <th>Spin</th>
                    <th>HB"</th>
                    <th>IVB"</th>
                    <th>Ext</th>
                  </tr>
                </thead>
                <tbody>
                  {[...summary.arsenal].sort((a, b) => b.count - a.count).map((a) => (
                    <tr key={a.pitch_type}>
                      <td>
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full border border-black/20 shrink-0"
                               style={{ backgroundColor: pitchColor(a.pitch_type) }} />
                          <span className="text-xs">{a.pitch_name || a.pitch_type}</span>
                        </div>
                      </td>
                      <td>{a.usage_pct}%</td>
                      <td>{a.avg_velo?.toFixed(1) ?? '–'}</td>
                      <td>{a.avg_spin ? Math.round(a.avg_spin) : '–'}</td>
                      <td>{a.avg_pfx_x != null ? (a.avg_pfx_x * 12).toFixed(1) : '–'}</td>
                      <td>{a.avg_pfx_z != null ? (a.avg_pfx_z * 12).toFixed(1) : '–'}</td>
                      <td>{a.avg_extension?.toFixed(1) ?? '–'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── LOCATION TAB ── */}
        {tab === 1 && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {/* All pitches */}
            <div>
              <div className="text-xs font-bangers tracking-wider text-gray-500 mb-2 uppercase">
                All Pitches ({filteredPitches.length})
              </div>
              <PitchLocationChart pitches={filteredPitches} height={320} />
            </div>
            {/* Split by pitch type */}
            {summary.arsenal.filter((a) => !selectedPitchType || a.pitch_type === selectedPitchType)
              .map((a) => {
                const pts = pitches.filter((p) => p.pitch_type === a.pitch_type)
                return (
                  <div key={a.pitch_type}>
                    <div className="text-xs font-bangers tracking-wider text-gray-500 mb-2 uppercase">
                      {a.pitch_name || a.pitch_type} ({pts.length})
                    </div>
                    <PitchLocationChart pitches={pts} height={320} />
                  </div>
                )
              })}
          </div>
        )}

        {/* ── MOVEMENT TAB ── */}
        {tab === 2 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <div className="text-xs font-bangers tracking-wider text-gray-500 mb-2 uppercase">
                All Pitches ({filteredPitches.length})
              </div>
              <PitchMovementChart pitches={filteredPitches} />
            </div>
            {/* Velocity over time by pitch type */}
            <div className="bg-sv-dark rounded p-3">
              <div className="text-white text-xs font-bangers tracking-wider mb-3">
                VELOCITY TREND (LAST 200 PITCHES)
              </div>
              <VeloTrendChart pitches={pitches.slice(0, 200).reverse()} arsenal={summary.arsenal} />
            </div>
          </div>
        )}

        {/* ── PITCH LOG TAB ── */}
        {tab === 3 && (
          <div className="bg-white border border-gray-200 rounded shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-bangers text-xl tracking-wider text-sv-dark">
                PITCH LOG ({logTotal.toLocaleString()} total)
              </h3>
              <div className="flex gap-2 items-center text-xs font-sans text-gray-500">
                <button
                  disabled={logOffset === 0}
                  onClick={() => setLogOffset(Math.max(0, logOffset - 200))}
                  className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-100"
                >← Prev</button>
                <span>Showing {logOffset + 1}–{Math.min(logOffset + 200, logTotal)}</span>
                <button
                  disabled={logOffset + 200 >= logTotal}
                  onClick={() => setLogOffset(logOffset + 200)}
                  className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-100"
                >Next →</button>
              </div>
            </div>
            <LeaderboardTable rows={pitches.slice(logOffset, logOffset + 200)} columns={PITCH_LOG_COLS} />
          </div>
        )}
      </div>
    </div>
  )
}

function PitchPill({ active, onClick, label, color }) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-3 py-1 rounded-full border-2 font-sans transition-all ${
        active ? 'text-white' : 'text-gray-600 border-gray-300 bg-white hover:border-gray-500'
      }`}
      style={active ? { backgroundColor: color, borderColor: color } : {}}
    >
      {label}
    </button>
  )
}

function VeloTrendChart({ pitches, arsenal }) {
  const data = pitches.map((p, i) => {
    const pt = p.pitch_type
    return { i, [pt]: p.release_speed }
  })

  const pitchTypes = arsenal.map((a) => a.pitch_type)

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ right: 10, left: -10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
        <XAxis dataKey="i" tick={{ fill: '#aaa', fontSize: 10 }} tickLine={false} />
        <YAxis domain={['auto', 'auto']} tick={{ fill: '#aaa', fontSize: 10 }} tickLine={false} />
        <Tooltip
          contentStyle={{ background: '#1a1a2e', border: '1px solid #444', color: '#fff', fontSize: 11 }}
          formatter={(v, name) => [v?.toFixed(1) + ' mph', PITCH_LABEL[name] || name]}
        />
        {pitchTypes.map((pt) => (
          <Line
            key={pt}
            type="monotone"
            dataKey={pt}
            stroke={pitchColor(pt)}
            dot={false}
            strokeWidth={1.5}
            connectNulls={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

import { useState } from 'react'
import { Link } from 'react-router-dom'

// Color scale: red (high) → blue (low), dark-theme compatible
function valueColor(val, min, max, higherIsBetter = true) {
  if (val == null || min == null || max == null || min === max) return ''
  const pct = (val - min) / (max - min)
  const adjusted = higherIsBetter ? pct : 1 - pct
  if (adjusted >= 0.85) return 'bg-red-900/40 text-red-300 font-semibold'
  if (adjusted >= 0.65) return 'bg-orange-900/20 text-orange-300'
  if (adjusted <= 0.15) return 'bg-blue-900/40 text-blue-300 font-semibold'
  if (adjusted <= 0.35) return 'bg-sky-900/20 text-sky-300'
  return ''
}

export default function LeaderboardTable({ rows = [], columns = [], defaultSort, linkTo }) {
  const [sortKey, setSortKey] = useState(defaultSort || columns[0]?.key)
  const [sortDir, setSortDir] = useState('desc')

  const handleSort = (key) => {
    if (sortKey === key) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else { setSortKey(key); setSortDir('desc') }
  }

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey]
    const bv = b[sortKey]
    if (av == null) return 1
    if (bv == null) return -1
    return sortDir === 'desc' ? bv - av : av - bv
  })

  // Pre-compute min/max for each numeric column
  const ranges = {}
  columns.forEach((col) => {
    if (col.colorScale) {
      const vals = rows.map((r) => r[col.key]).filter((v) => v != null)
      ranges[col.key] = { min: Math.min(...vals), max: Math.max(...vals) }
    }
  })

  return (
    <div className="overflow-x-auto">
      <table className="savant-table">
        <thead>
          <tr>
            <th className="w-8 text-center">#</th>
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                style={sortKey === col.key ? { background: 'rgba(14,165,233,0.20)', color: '#0EA5E9' } : {}}
                title={col.description}
              >
                <span className="flex items-center gap-1">
                  {col.label}
                  {sortKey === col.key && (
                    <span className="opacity-70 text-xs">{sortDir === 'desc' ? '▼' : '▲'}</span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i}>
              <td className="text-center text-mist text-xs">{i + 1}</td>
              {columns.map((col) => {
                const val = row[col.key]
                const colorClass = col.colorScale
                  ? valueColor(val, ranges[col.key]?.min, ranges[col.key]?.max, col.higherIsBetter !== false)
                  : ''

                if (col.key === 'pitcher_name' || col.key === 'batter_name') {
                  const id = row.pitcher_id || row.batter_id
                  const basePath = col.key === 'pitcher_name' ? '/sports/mlb/pitcher' : '/sports/mlb/batter'
                  return (
                    <td key={col.key} className={colorClass}>
                      {linkTo && id ? (
                        <Link
                          to={`${basePath}/${id}`}
                          className="text-electric hover:underline font-medium"
                        >
                          {val ?? '–'}
                        </Link>
                      ) : (
                        val ?? '–'
                      )}
                    </td>
                  )
                }

                return (
                  <td key={col.key} className={colorClass}>
                    {val != null ? (col.format ? col.format(val) : val) : '–'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {sorted.length === 0 && (
        <div className="text-center py-12 text-mist text-sm">
          No data — check filters or wait for the data pipeline to run.
        </div>
      )}
    </div>
  )
}

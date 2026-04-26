import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { savantColor, percentileRank } from '../../lib/savantColor'

/**
 * Baseball Savant-style leaderboard table.
 *
 * Columns flagged with `colorScale: true` get a diverging red↔blue percentile
 * gradient per column. `higherIsBetter` flips the scale for negative stats
 * like xwOBA allowed.
 */
export default function LeaderboardTable({ rows = [], columns = [], defaultSort, linkTo }) {
  const [sortKey, setSortKey] = useState(defaultSort || columns[0]?.key)
  const [sortDir, setSortDir] = useState('desc')

  const handleSort = (key) => {
    if (sortKey === key) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else { setSortKey(key); setSortDir('desc') }
  }

  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey]
      if (av == null) return 1
      if (bv == null) return -1
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortDir === 'desc' ? bv.localeCompare(av) : av.localeCompare(bv)
      }
      return sortDir === 'desc' ? bv - av : av - bv
    })
  }, [rows, sortKey, sortDir])

  // Pre-sort each numeric column for percentile computation
  const colRanges = useMemo(() => {
    const r = {}
    columns.forEach((col) => {
      if (col.colorScale) {
        const vals = rows.map((row) => row[col.key]).filter((v) => v != null).sort((a, b) => a - b)
        r[col.key] = vals
      }
    })
    return r
  }, [rows, columns])

  return (
    <div className="overflow-x-auto">
      <table className="savant-table">
        <thead>
          <tr>
            <th className="w-8 text-center">#</th>
            {columns.map((col) => {
              const isActive = sortKey === col.key
              return (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  title={col.description}
                  style={
                    isActive
                      ? { background: 'rgba(0,102,204,0.10)', color: '#0066CC' }
                      : undefined
                  }
                >
                  <span className="flex items-center gap-1">
                    {col.label}
                    {isActive && (
                      <span className="opacity-70 text-xs">{sortDir === 'desc' ? '▼' : '▲'}</span>
                    )}
                  </span>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i}>
              <td className="text-center text-xs" style={{ color: '#86868B' }}>{i + 1}</td>
              {columns.map((col) => {
                const val = row[col.key]
                let style = undefined
                if (col.colorScale && colRanges[col.key]) {
                  const pct = percentileRank(val, colRanges[col.key])
                  if (pct != null) style = savantColor(pct, col.higherIsBetter !== false)
                }

                if (col.key === 'pitcher_name' || col.key === 'batter_name') {
                  const id = row.pitcher_id || row.batter_id
                  const basePath = col.key === 'pitcher_name' ? '/sports/mlb/pitcher' : '/sports/mlb/batter'
                  return (
                    <td key={col.key} style={style}>
                      {linkTo && id ? (
                        <Link
                          to={`${basePath}/${id}`}
                          className="font-medium hover:underline"
                          style={{ color: '#0066CC' }}
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
                  <td key={col.key} style={style} className="tabular-nums">
                    {val != null ? (col.format ? col.format(val) : val) : '–'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {sorted.length === 0 && (
        <div className="text-center py-12 text-sm" style={{ color: '#86868B' }}>
          No data — check filters or wait for the data pipeline to run.
        </div>
      )}
    </div>
  )
}

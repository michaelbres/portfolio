import { useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../../components/Navbar'
import PageHeader from '../../components/PageHeader'
import api from '../../lib/api'

// ── Constants ─────────────────────────────────────────────────────────────────

const SPORTS = [
  { value: 'all',        label: 'All Sports' },
  { value: 'football',   label: 'Football'   },
  { value: 'baseball',   label: 'Baseball'   },
  { value: 'basketball', label: 'Basketball' },
]

const SEARCH_MODES = ['Player', 'Set']

const DAYS_OPTIONS = [30, 60, 90, 180, 365]

const CONF_STYLES = {
  high:   { bg: 'rgba(40,205,65,0.10)',  color: '#027A48', border: 'rgba(40,205,65,0.25)'  },
  medium: { bg: 'rgba(234,179,8,0.10)',  color: '#92400E', border: 'rgba(234,179,8,0.40)'  },
  low:    { bg: 'rgba(239,68,68,0.08)',  color: '#B42318', border: 'rgba(239,68,68,0.25)'  },
  none:   { bg: 'rgba(134,134,139,0.10)',color: '#86868B', border: 'rgba(134,134,139,0.25)'},
}

const cardStyle = {
  background: '#FFFFFF',
  border: '1px solid rgba(0,0,0,0.08)',
  borderRadius: '14px',
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v) {
  if (v == null) return '–'
  return '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

function ConfBadge({ confidence }) {
  const c = CONF_STYLES[confidence] || CONF_STYLES.none
  const label = { high: 'High', medium: 'Medium', low: 'Low', none: '–' }[confidence] || '–'
  return (
    <span className="text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.border}` }}>
      {label}
    </span>
  )
}

function InsertBadge({ insertType, isRookie, isAuto, isPatch }) {
  const isAP = isPatch && isAuto
  const color = isAP ? '#B42318' : isAuto ? '#0066CC' : '#86868B'
  const bg    = isAP ? 'rgba(180,35,24,0.08)' : isAuto ? 'rgba(0,102,204,0.08)' : 'rgba(134,134,139,0.08)'
  const border= isAP ? 'rgba(180,35,24,0.20)' : isAuto ? 'rgba(0,102,204,0.20)' : 'rgba(134,134,139,0.20)'
  return (
    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
      style={{ background: bg, color, border: `1px solid ${border}` }}>
      {insertType || 'Base'}
      {isRookie && <span className="ml-1 opacity-75">RC</span>}
    </span>
  )
}

// ── Sales detail panel ────────────────────────────────────────────────────────

function SalesPanel({ group, onClose }) {
  return (
    <div style={{ ...cardStyle, marginTop: 0 }}>
      <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
        <div>
          <span className="font-semibold text-sm" style={{ color: '#1D1D1F' }}>
            {group.year} {group.set_name || 'Unknown Set'} — {group.insert_type}
            {group.print_run ? ` /${group.print_run}` : ''}
            {group.grade ? ` (${group.grade})` : ''}
          </span>
          <span className="ml-2 text-xs" style={{ color: '#86868B' }}>
            {group.stats.sale_count} sale{group.stats.sale_count !== 1 ? 's' : ''}
          </span>
        </div>
        <button onClick={onClose} className="text-lg leading-none px-1" style={{ color: '#86868B' }}
          onMouseEnter={e => { e.currentTarget.style.color = '#1D1D1F' }}
          onMouseLeave={e => { e.currentTarget.style.color = '#86868B' }}>×</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: '#F5F5F7', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
              <th className="text-left py-2 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Date</th>
              <th className="text-right py-2 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Price</th>
              <th className="text-left py-2 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Title</th>
              <th className="py-2 px-4 w-12" />
            </tr>
          </thead>
          <tbody>
            {group.sales.map((s, i) => (
              <tr key={i} style={{ borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
                <td className="py-2 px-4 font-mono text-xs whitespace-nowrap" style={{ color: '#86868B' }}>
                  {s.sold_at || '–'}
                </td>
                <td className="py-2 px-4 text-right font-mono font-semibold text-sm" style={{ color: '#1D1D1F' }}>
                  ${Number(s.price).toLocaleString()}
                </td>
                <td className="py-2 px-4 text-xs max-w-xs truncate" style={{ color: '#86868B' }} title={s.title}>
                  {s.title}
                </td>
                <td className="py-2 px-4 text-center">
                  {s.url && (
                    <a href={s.url} target="_blank" rel="noopener noreferrer"
                      className="text-xs" style={{ color: '#0066CC' }}>↗</a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Results table ─────────────────────────────────────────────────────────────

function ResultsTable({ groups, totalSales, query, days }) {
  const [expanded, setExpanded] = useState(null)

  if (!groups.length) {
    return (
      <div style={cardStyle} className="p-8 text-center">
        <p className="text-sm" style={{ color: '#86868B' }}>No completed sales found for <strong style={{ color: '#1D1D1F' }}>{query}</strong> in the last {days} days.</p>
        <p className="text-xs mt-1" style={{ color: '#86868B', opacity: 0.75 }}>Try a broader search, different sport, or longer date range.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Summary bar */}
      <div className="flex items-center justify-between text-xs" style={{ color: '#86868B' }}>
        <span><strong style={{ color: '#1D1D1F' }}>{totalSales}</strong> sales → <strong style={{ color: '#1D1D1F' }}>{groups.length}</strong> card groups</span>
        <span>Last {days} days</span>
      </div>

      {/* Table */}
      <div style={cardStyle}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: '#F5F5F7', borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
                <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Year / Set</th>
                <th className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Card Type</th>
                <th className="text-center py-3 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Print Run</th>
                <th className="text-right py-3 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Sales</th>
                <th className="text-right py-3 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Avg Sale</th>
                <th className="text-right py-3 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Last Sale</th>
                <th className="text-right py-3 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Fair Value</th>
                <th className="text-center py-3 px-4 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g, i) => {
                const isOpen = expanded === g.key
                const fv = g.fair_value || {}
                return (
                  <>
                    <tr
                      key={g.key}
                      onClick={() => setExpanded(isOpen ? null : g.key)}
                      className="cursor-pointer transition-colors duration-100"
                      style={{
                        borderBottom: isOpen ? 'none' : '1px solid rgba(0,0,0,0.04)',
                        background: isOpen ? 'rgba(0,102,204,0.04)' : undefined,
                      }}
                      onMouseEnter={e => { if (!isOpen) e.currentTarget.style.background = '#F9F9FB' }}
                      onMouseLeave={e => { if (!isOpen) e.currentTarget.style.background = '' }}
                    >
                      {/* Year / Set */}
                      <td className="py-3 px-4">
                        <div className="font-medium text-sm" style={{ color: '#1D1D1F' }}>
                          {g.year || '–'}
                        </div>
                        <div className="text-xs truncate max-w-[160px]" style={{ color: '#86868B' }} title={g.set_name}>
                          {g.set_name || 'Unknown Set'}
                        </div>
                      </td>

                      {/* Card Type */}
                      <td className="py-3 px-4">
                        <InsertBadge
                          insertType={g.insert_type}
                          isRookie={g.is_rookie}
                          isAuto={g.is_auto}
                          isPatch={g.is_patch}
                        />
                        {g.grade && (
                          <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(105,65,198,0.08)', color: '#6941C6', border: '1px solid rgba(105,65,198,0.20)' }}>
                            {g.grade}
                          </span>
                        )}
                      </td>

                      {/* Print Run */}
                      <td className="py-3 px-4 text-center">
                        <span className="font-mono text-sm font-semibold" style={{ color: g.print_run ? '#1D1D1F' : '#86868B' }}>
                          {g.print_run ? `/${g.print_run}` : 'unnumbered'}
                        </span>
                      </td>

                      {/* Sales */}
                      <td className="py-3 px-4 text-right font-mono text-sm" style={{ color: '#1D1D1F' }}>
                        {g.stats.sale_count}
                      </td>

                      {/* Avg Sale */}
                      <td className="py-3 px-4 text-right font-mono text-sm" style={{ color: '#1D1D1F' }}>
                        {fmt(g.stats.avg_price)}
                      </td>

                      {/* Last Sale */}
                      <td className="py-3 px-4 text-right">
                        <div className="font-mono text-sm font-semibold" style={{ color: '#1D1D1F' }}>{fmt(g.stats.last_price)}</div>
                        {g.stats.last_sale_date && (
                          <div className="text-xs" style={{ color: '#86868B' }}>{g.stats.last_sale_date}</div>
                        )}
                      </td>

                      {/* Fair Value */}
                      <td className="py-3 px-4 text-right">
                        <div className="font-mono text-sm font-semibold" style={{ color: fv.value ? '#0066CC' : '#86868B' }}>
                          {fv.value ? fmt(fv.value) : '–'}
                        </div>
                        {fv.method === 'print_run_ratio' && (
                          <div className="text-xs" style={{ color: '#86868B' }} title={fv.anchor_label}>ratio est.</div>
                        )}
                      </td>

                      {/* Confidence */}
                      <td className="py-3 px-4 text-center">
                        <ConfBadge confidence={fv.confidence || 'none'} />
                      </td>
                    </tr>

                    {/* Expanded sales panel */}
                    {isOpen && (
                      <tr key={`${g.key}-detail`}>
                        <td colSpan={8} style={{ padding: '0 16px 16px', background: 'rgba(0,102,204,0.04)' }}>
                          <SalesPanel group={g} onClose={() => setExpanded(null)} />
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Fair value legend */}
      <div className="text-xs flex flex-wrap gap-4 pt-1" style={{ color: '#86868B' }}>
        <span><strong style={{ color: '#1D1D1F' }}>Fair value</strong> = recency-weighted avg of recent sales</span>
        <span style={{ color: '#D2D2D7' }}>·</span>
        <span><strong style={{ color: '#1D1D1F' }}>Ratio est.</strong> = scarcity model from comparable print runs</span>
        <span style={{ color: '#D2D2D7' }}>·</span>
        <span>Click any row to see individual sales</span>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Cards() {
  const [mode, setMode]       = useState(0)     // 0=Player, 1=Set
  const [query, setQuery]     = useState('')
  const [sport, setSport]     = useState('all')
  const [days, setDays]       = useState(90)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const inputRef = useRef(null)

  async function search(e) {
    e?.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResults(null)
    try {
      const endpoint = mode === 0 ? '/api/cards/player-search' : '/api/cards/set-search'
      const param    = mode === 0 ? 'name' : 'name'
      const { data } = await api.get(endpoint, { params: { [param]: query.trim(), sport, days } })
      setResults(data)
    } catch (e) {
      const msg = e?.response?.data?.detail || 'Search failed.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen" style={{ background: '#F5F5F7' }}>
      <Navbar />

      <PageHeader
        kicker="Cards"
        kickerColor="#92400E"
        kickerBg="rgba(234,179,8,0.12)"
        title="Card Market"
        subtitle="Search eBay completed sales by player or set. Fair values estimated from recent sales using print-run scarcity ratios and your custom hierarchy."
        right={
          <Link to="/cards/hierarchy"
            className="px-3.5 py-1.5 rounded-full text-sm font-medium transition-all duration-150"
            style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.12)', color: '#1D1D1F', textDecoration: 'none' }}>
            Edit Hierarchy
          </Link>
        }
      />

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-5">

        {/* Search card */}
        <div style={cardStyle} className="p-5">
          {/* Mode tabs */}
          <div className="inline-flex rounded-full p-1 mb-4" style={{ background: '#E8E8ED' }}>
            {SEARCH_MODES.map((m, i) => (
              <button key={m} onClick={() => { setMode(i); setResults(null); setError(null) }}
                className="px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-150"
                style={mode === i
                  ? { background: '#FFFFFF', color: '#1D1D1F', boxShadow: '0 1px 3px rgba(0,0,0,0.12)' }
                  : { background: 'transparent', color: '#86868B' }}>
                {m}
              </button>
            ))}
          </div>

          {/* Search form */}
          <form onSubmit={search} className="flex flex-wrap gap-2 items-end">
            {/* Main input */}
            <div className="flex-1 min-w-[220px]">
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#86868B' }}>
                {mode === 0 ? 'Player Name' : 'Set Name'}
              </label>
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder={mode === 0 ? 'e.g. Shedeur Sanders' : 'e.g. Panini Prizm 2024'}
                className="w-full px-3.5 py-2.5 text-sm rounded-xl focus:outline-none"
                style={{
                  background: '#F5F5F7',
                  border: '1px solid rgba(0,0,0,0.12)',
                  color: '#1D1D1F',
                }}
                onFocus={e => { e.target.style.borderColor = 'rgba(0,102,204,0.40)'; e.target.style.background = '#FFFFFF' }}
                onBlur={e  => { e.target.style.borderColor = 'rgba(0,0,0,0.12)';    e.target.style.background = '#F5F5F7' }}
              />
            </div>

            {/* Sport filter */}
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#86868B' }}>Sport</label>
              <div className="flex gap-1.5">
                {SPORTS.map(s => (
                  <button key={s.value} type="button" onClick={() => setSport(s.value)}
                    className="px-3 py-2 rounded-xl text-xs font-medium transition-all duration-150 whitespace-nowrap"
                    style={sport === s.value
                      ? { background: 'rgba(0,102,204,0.10)', color: '#0066CC', border: '1px solid rgba(0,102,204,0.25)' }
                      : { background: '#F5F5F7', color: '#86868B', border: '1px solid rgba(0,0,0,0.08)' }}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Days */}
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#86868B' }}>Date Range</label>
              <select value={days} onChange={e => setDays(Number(e.target.value))}
                className="px-3 py-2.5 text-sm rounded-xl focus:outline-none"
                style={{ background: '#F5F5F7', border: '1px solid rgba(0,0,0,0.12)', color: '#1D1D1F' }}>
                {DAYS_OPTIONS.map(d => <option key={d} value={d}>Last {d} days</option>)}
              </select>
            </div>

            {/* Submit */}
            <button type="submit" disabled={loading || !query.trim()}
              className="px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 disabled:opacity-50"
              style={{ background: '#0066CC', color: '#FFFFFF' }}>
              {loading ? 'Searching…' : 'Search'}
            </button>
          </form>
        </div>

        {/* Error */}
        {error && (
          <div className="px-4 py-3 text-sm rounded-xl"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', color: '#B42318' }}>
            {error}
            {error.includes('EBAY_APP_ID') && (
              <span className="block mt-1 text-xs">
                Add <code className="font-mono bg-red-50 px-1 rounded">EBAY_APP_ID=your_key</code> to <code className="font-mono bg-red-50 px-1 rounded">backend/.env</code> and restart the backend.
              </span>
            )}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div style={cardStyle} className="p-8 text-center">
            <div className="text-sm animate-pulse" style={{ color: '#86868B' }}>
              Fetching eBay completed sales for <strong style={{ color: '#1D1D1F' }}>{query}</strong>…
            </div>
          </div>
        )}

        {/* Results */}
        {!loading && results && (
          <ResultsTable
            groups={results.groups}
            totalSales={results.total_sales}
            query={query}
            days={days}
          />
        )}

        {/* Empty state */}
        {!loading && !results && !error && (
          <div style={cardStyle} className="p-10 text-center">
            <div className="text-3xl mb-3">🃏</div>
            <p className="font-medium text-sm" style={{ color: '#1D1D1F' }}>Search by player or set</p>
            <p className="text-xs mt-1" style={{ color: '#86868B' }}>
              Pulls last 90 days of eBay completed sales, groups by card type, and estimates fair value using print-run scarcity ratios.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

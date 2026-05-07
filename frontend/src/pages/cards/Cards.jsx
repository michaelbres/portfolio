import { useState, useEffect, useCallback } from 'react'
import Navbar from '../../components/Navbar'
import PageHeader from '../../components/PageHeader'
import api from '../../lib/api'

// ── Constants ─────────────────────────────────────────────────────────────────

const SPORTS = ['all', 'baseball', 'football', 'basketball', 'pokemon']

const SPORT_LABELS = {
  all: 'All', baseball: 'Baseball', football: 'Football',
  basketball: 'Basketball', pokemon: 'Pokémon',
}

const SPORT_COLORS = {
  all:        { bg: 'rgba(134,134,139,0.10)', color: '#86868B', border: 'rgba(134,134,139,0.25)' },
  baseball:   { bg: 'rgba(0,102,204,0.10)',   color: '#0066CC', border: 'rgba(0,102,204,0.25)'   },
  football:   { bg: 'rgba(180,35,24,0.10)',   color: '#B42318', border: 'rgba(180,35,24,0.25)'   },
  basketball: { bg: 'rgba(234,88,12,0.10)',   color: '#EA580C', border: 'rgba(234,88,12,0.25)'   },
  pokemon:    { bg: 'rgba(234,179,8,0.10)',   color: '#92400E', border: 'rgba(234,179,8,0.40)'   },
}

const TABS = ['Set Tiers', 'Card Types', 'Special Flags']

const cardStyle = { background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.08)', borderRadius: '14px' }
const inputStyle = {
  background: '#F5F5F7', border: '1px solid rgba(0,0,0,0.10)',
  borderRadius: '6px', color: '#1D1D1F', fontSize: '13px',
  padding: '4px 8px', outline: 'none', width: '100%',
}
const numInputStyle = { ...inputStyle, width: '60px', textAlign: 'center' }

// ── Sport badge ────────────────────────────────────────────────────────────────

function SportBadge({ sport }) {
  const c = SPORT_COLORS[sport] || SPORT_COLORS.all
  return (
    <span className="text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.border}` }}>
      {SPORT_LABELS[sport] || sport}
    </span>
  )
}

// ── Editable cell helpers ──────────────────────────────────────────────────────

function EditText({ value, onChange, placeholder = '' }) {
  return (
    <input type="text" value={value ?? ''} placeholder={placeholder}
      onChange={e => onChange(e.target.value)}
      style={inputStyle}
      onFocus={e => { e.target.style.borderColor = 'rgba(0,102,204,0.40)' }}
      onBlur={e  => { e.target.style.borderColor = 'rgba(0,0,0,0.10)'    }}
    />
  )
}

function EditNum({ value, onChange, min, max, step = 1 }) {
  return (
    <input type="number" value={value ?? ''} min={min} max={max} step={step}
      onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))}
      style={numInputStyle}
      onFocus={e => { e.target.style.borderColor = 'rgba(0,102,204,0.40)' }}
      onBlur={e  => { e.target.style.borderColor = 'rgba(0,0,0,0.10)'    }}
    />
  )
}

function DeleteBtn({ onClick }) {
  return (
    <button onClick={onClick}
      className="text-xs transition-colors duration-150 px-1"
      style={{ color: '#86868B' }}
      onMouseEnter={e => { e.currentTarget.style.color = '#B42318' }}
      onMouseLeave={e => { e.currentTarget.style.color = '#86868B' }}
    >×</button>
  )
}

// ── Set Tiers table ────────────────────────────────────────────────────────────

function SetTiersTab({ rows, onChange }) {
  const [sportFilter, setSportFilter] = useState('all')

  const visible = sportFilter === 'all' ? rows : rows.filter(r => r.sport === sportFilter)

  const update = (id, field, val) =>
    onChange(rows.map(r => r._key === id ? { ...r, [field]: val } : r))

  const remove = id => onChange(rows.filter(r => r._key !== id))

  const add = () => onChange([...rows, {
    _key: Date.now(), set_name: '', sport: sportFilter === 'all' ? 'baseball' : sportFilter,
    tier: Math.max(...rows.map(r => r.tier), 0) + 1, notes: '',
  }])

  return (
    <div>
      {/* Sport filter */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {SPORTS.map(s => (
          <button key={s} onClick={() => setSportFilter(s)}
            className="px-3 py-1 rounded-full text-xs font-medium transition-all duration-150"
            style={sportFilter === s
              ? { background: SPORT_COLORS[s].bg, color: SPORT_COLORS[s].color, border: `1px solid ${SPORT_COLORS[s].border}` }
              : { background: '#F5F5F7', color: '#86868B', border: '1px solid rgba(0,0,0,0.08)' }
            }
          >{SPORT_LABELS[s]}</button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
              <th className="text-left py-2 px-2 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B', width: '40%' }}>Set / Product</th>
              <th className="text-left py-2 px-2 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B', width: '14%' }}>Sport</th>
              <th className="text-center py-2 px-2 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B', width: '8%' }}>Tier ↓</th>
              <th className="text-left py-2 px-2 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Notes</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {visible.map(row => (
              <tr key={row._key} style={{ borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
                <td className="py-1.5 px-2">
                  <EditText value={row.set_name} onChange={v => update(row._key, 'set_name', v)} placeholder="Set name" />
                </td>
                <td className="py-1.5 px-2">
                  <select value={row.sport} onChange={e => update(row._key, 'sport', e.target.value)}
                    style={{ ...inputStyle, width: 'auto' }}>
                    {SPORTS.filter(s => s !== 'all').map(s =>
                      <option key={s} value={s}>{SPORT_LABELS[s]}</option>
                    )}
                  </select>
                </td>
                <td className="py-1.5 px-2 text-center">
                  <EditNum value={row.tier} min={1} max={99} onChange={v => update(row._key, 'tier', v)} />
                </td>
                <td className="py-1.5 px-2">
                  <EditText value={row.notes} onChange={v => update(row._key, 'notes', v)} placeholder="Optional notes" />
                </td>
                <td className="py-1.5 px-2 text-center">
                  <DeleteBtn onClick={() => remove(row._key)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button onClick={add} className="mt-3 text-xs font-medium transition-colors duration-150"
        style={{ color: '#0066CC' }}
        onMouseEnter={e => { e.currentTarget.style.opacity = '0.7' }}
        onMouseLeave={e => { e.currentTarget.style.opacity = '1'   }}
      >+ Add set</button>

      <p className="mt-3 text-xs" style={{ color: '#86868B' }}>
        Tier 1 = most desirable. Lower number = higher prestige. Used to compare cards across different products.
      </p>
    </div>
  )
}

// ── Card Types table ───────────────────────────────────────────────────────────

function CardTypesTab({ rows, onChange }) {
  const update = (id, field, val) =>
    onChange(rows.map(r => r._key === id ? { ...r, [field]: val } : r))

  const remove = id => onChange(rows.filter(r => r._key !== id))

  const add = () => onChange([...rows, {
    _key: Date.now(), insert_name: '',
    rank: Math.max(...rows.map(r => r.rank), 0) + 1, notes: '',
  }])

  const sorted = [...rows].sort((a, b) => a.rank - b.rank)

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
              <th className="text-center py-2 px-2 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B', width: '8%' }}>Rank ↓</th>
              <th className="text-left py-2 px-2 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B', width: '35%' }}>Card Type / Parallel</th>
              <th className="text-left py-2 px-2 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Notes</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {sorted.map(row => (
              <tr key={row._key} style={{ borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
                <td className="py-1.5 px-2 text-center">
                  <EditNum value={row.rank} min={1} max={99} onChange={v => update(row._key, 'rank', v)} />
                </td>
                <td className="py-1.5 px-2">
                  <EditText value={row.insert_name} onChange={v => update(row._key, 'insert_name', v)} placeholder="Card type name" />
                </td>
                <td className="py-1.5 px-2">
                  <EditText value={row.notes} onChange={v => update(row._key, 'notes', v)} placeholder="Optional notes" />
                </td>
                <td className="py-1.5 px-2 text-center">
                  <DeleteBtn onClick={() => remove(row._key)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button onClick={add} className="mt-3 text-xs font-medium transition-colors duration-150"
        style={{ color: '#0066CC' }}
        onMouseEnter={e => { e.currentTarget.style.opacity = '0.7' }}
        onMouseLeave={e => { e.currentTarget.style.opacity = '1'   }}
      >+ Add card type</button>

      <p className="mt-3 text-xs" style={{ color: '#86868B' }}>
        Rank 1 = most desirable. Print run (/5, /10, etc.) is handled separately — lower always = more valuable.
      </p>
    </div>
  )
}

// ── Special Flags table ────────────────────────────────────────────────────────

function SpecialFlagsTab({ rows, onChange }) {
  const update = (id, field, val) =>
    onChange(rows.map(r => r._key === id ? { ...r, [field]: val } : r))

  const remove = id => onChange(rows.filter(r => r._key !== id))

  const add = () => onChange([...rows, {
    _key: Date.now(), flag_name: '', multiplier: 1.0, description: '',
  }])

  const sorted = [...rows].sort((a, b) => b.multiplier - a.multiplier)

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
              <th className="text-left py-2 px-2 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B', width: '30%' }}>Designation</th>
              <th className="text-center py-2 px-2 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B', width: '10%' }}>Multiplier</th>
              <th className="text-left py-2 px-2 text-xs font-semibold uppercase tracking-wider" style={{ color: '#86868B' }}>Description</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {sorted.map(row => (
              <tr key={row._key} style={{ borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
                <td className="py-1.5 px-2">
                  <EditText value={row.flag_name} onChange={v => update(row._key, 'flag_name', v)} placeholder="Flag name" />
                </td>
                <td className="py-1.5 px-2">
                  <EditNum value={row.multiplier} min={0.1} max={10} step={0.05} onChange={v => update(row._key, 'multiplier', v)} />
                </td>
                <td className="py-1.5 px-2">
                  <EditText value={row.description} onChange={v => update(row._key, 'description', v)} placeholder="What this flag means" />
                </td>
                <td className="py-1.5 px-2 text-center">
                  <DeleteBtn onClick={() => remove(row._key)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button onClick={add} className="mt-3 text-xs font-medium transition-colors duration-150"
        style={{ color: '#0066CC' }}
        onMouseEnter={e => { e.currentTarget.style.opacity = '0.7' }}
        onMouseLeave={e => { e.currentTarget.style.opacity = '1'   }}
      >+ Add flag</button>

      <p className="mt-3 text-xs" style={{ color: '#86868B' }}>
        Multiplier applied to a card's estimated fair value. 1.0 = no effect. 2.5 = rookie card commands 2.5× premium.
      </p>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

function keyRows(rows, keyField) {
  return rows.map((r, i) => ({ ...r, _key: r.id ?? `new-${i}-${Date.now()}` }))
}

export default function Cards() {
  const [tab, setTab]       = useState(0)
  const [sets, setSets]     = useState([])
  const [inserts, setInserts] = useState([])
  const [flags, setFlags]   = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving]  = useState(false)
  const [saved, setSaved]    = useState(false)
  const [error, setError]    = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/api/cards/hierarchy')
      setSets(keyRows(data.sets))
      setInserts(keyRows(data.inserts))
      setFlags(keyRows(data.flags))
    } catch {
      setError('Failed to load hierarchy data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function save() {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      await api.put('/api/cards/hierarchy', {
        sets:    sets.map(({ _key, ...r }) => r),
        inserts: inserts.map(({ _key, ...r }) => r),
        flags:   flags.map(({ _key, ...r }) => r),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
      load()
    } catch {
      setError('Failed to save.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen" style={{ background: '#F5F5F7' }}>
      <Navbar />

      <PageHeader
        kicker="Cards"
        kickerColor="#92400E"
        kickerBg="rgba(234,179,8,0.12)"
        title="Card Hierarchy"
        subtitle="Define how sets, card types, and special designations rank relative to each other. Used to estimate fair market value for cards with thin sales data."
        right={
          <div className="flex items-center gap-2">
            {saved && (
              <span className="text-xs px-2.5 py-1 rounded-full"
                style={{ background: 'rgba(40,205,65,0.10)', color: '#027A48', border: '1px solid rgba(40,205,65,0.25)' }}>
                Saved
              </span>
            )}
            <button onClick={save} disabled={saving || loading}
              className="px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-150 disabled:opacity-50"
              style={{ background: '#0066CC', color: '#fff', border: 'none' }}>
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        }
      />

      <div className="max-w-7xl mx-auto px-6 py-6">
        {error && (
          <div className="mb-4 px-4 py-3 text-sm rounded-xl"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', color: '#B42318' }}>
            {error}
          </div>
        )}

        {/* Tab bar */}
        <div className="inline-flex rounded-full p-1 mb-6"
          style={{ background: '#E8E8ED' }}>
          {TABS.map((t, i) => (
            <button key={t} onClick={() => setTab(i)}
              className="px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-150 whitespace-nowrap"
              style={tab === i
                ? { background: '#FFFFFF', color: '#1D1D1F', boxShadow: '0 1px 3px rgba(0,0,0,0.12)' }
                : { background: 'transparent', color: '#86868B' }
              }
            >{t}</button>
          ))}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <span className="text-sm animate-pulse" style={{ color: '#86868B' }}>Loading hierarchy…</span>
          </div>
        ) : (
          <div style={cardStyle} className="p-6">
            {tab === 0 && <SetTiersTab    rows={sets}    onChange={setSets}    />}
            {tab === 1 && <CardTypesTab   rows={inserts} onChange={setInserts} />}
            {tab === 2 && <SpecialFlagsTab rows={flags}  onChange={setFlags}   />}
          </div>
        )}

        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-4 text-xs" style={{ color: '#86868B' }}>
          {SPORTS.filter(s => s !== 'all').map(s => (
            <span key={s} className="flex items-center gap-1.5">
              <span className="inline-block w-2 h-2 rounded-full"
                style={{ background: SPORT_COLORS[s].color }} />
              {SPORT_LABELS[s]}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

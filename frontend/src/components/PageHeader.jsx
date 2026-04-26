/**
 * PageHeader — shared top-of-page section used across all inner pages.
 *
 * Apple light theme: white surface, subtle bottom hairline, kicker + title + subtitle.
 * Accepts optional `right` content (selects, stats, buttons) aligned right.
 *
 * Use this on every inner page so the top of the site looks uniform.
 */
export default function PageHeader({
  kicker,
  kickerColor = '#0066CC',
  kickerBg    = 'rgba(0,102,204,0.10)',
  title,
  subtitle,
  breadcrumbs,
  right,
}) {
  return (
    <div
      style={{
        background: '#FFFFFF',
        borderBottom: '1px solid rgba(0,0,0,0.08)',
      }}
    >
      <div className="max-w-7xl mx-auto px-6 py-7">
        {breadcrumbs && (
          <div className="flex items-center gap-2 text-xs mb-3" style={{ color: '#86868B' }}>
            {breadcrumbs.map((b, i) => (
              <span key={i} className="flex items-center gap-2">
                {b.href ? (
                  <a href={b.href} className="transition-colors hover:opacity-70" style={{ color: '#86868B' }}>
                    {b.label}
                  </a>
                ) : (
                  <span style={{ color: '#1D1D1F' }}>{b.label}</span>
                )}
                {i < breadcrumbs.length - 1 && <span>›</span>}
              </span>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            {kicker && (
              <span
                className="inline-block text-[11px] font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full mb-2"
                style={{
                  background: kickerBg,
                  color: kickerColor,
                }}
              >
                {kicker}
              </span>
            )}
            <h1
              className="tracking-tight"
              style={{
                fontWeight: 600,
                fontSize: 'clamp(1.5rem, 3vw, 2rem)',
                color: '#1D1D1F',
                letterSpacing: '-0.02em',
                lineHeight: 1.15,
              }}
            >
              {title}
            </h1>
            {subtitle && (
              <p className="text-sm mt-1.5 max-w-2xl" style={{ color: '#86868B' }}>
                {subtitle}
              </p>
            )}
          </div>
          {right && <div className="flex-shrink-0">{right}</div>}
        </div>
      </div>
    </div>
  )
}

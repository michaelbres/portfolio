// /home/user/portfolio/frontend/src/components/Navbar.jsx
import { Link, useLocation } from 'react-router-dom'

const LINKS = [
  { to: '/',                        label: 'Home' },
  { to: '/sports',                  label: 'Sports Analytics' },
  { to: '/sports/mlb/fair-value',   label: 'Fair Value' },
  { to: '/sports/mlb/stuff-plus',   label: 'Stuff+' },
  { to: '/betting',                 label: 'Betting' },
]

export default function Navbar() {
  const { pathname } = useLocation()

  return (
    <nav
      className="sticky top-0 z-50"
      style={{
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        backgroundColor: 'rgba(8, 8, 8, 0.85)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
      }}
    >
      <div className="max-w-7xl mx-auto px-5 flex items-center gap-8 h-14">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 shrink-0 group">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm tracking-tight"
            style={{
              background: 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
              color: '#fff',
              boxShadow: '0 0 12px rgba(14,165,233,0.35)',
            }}
          >
            MB
          </div>
          <span
            className="text-snow font-semibold text-sm tracking-tight hidden sm:block"
            style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif' }}
          >
            Breslow Analytics
          </span>
        </Link>

        {/* Nav links */}
        <div className="flex items-center gap-1 ml-auto">
          {LINKS.map(({ to, label }) => {
            // Exact match for home, prefix match for everything else
            const active =
              to === '/'
                ? pathname === '/'
                : pathname === to || pathname.startsWith(to + '/')

            return (
              <Link
                key={to}
                to={to}
                className={[
                  'relative px-3.5 py-1.5 text-sm rounded-lg transition-colors duration-150',
                  active
                    ? 'text-electric'
                    : 'text-mist hover:text-snow',
                ].join(' ')}
                style={{
                  fontFamily:
                    '-apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif',
                  fontWeight: active ? 500 : 400,
                  backgroundColor: active
                    ? 'rgba(14, 165, 233, 0.10)'
                    : undefined,
                }}
              >
                {label}
                {/* Active underline accent */}
                {active && (
                  <span
                    className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5 rounded-full"
                    style={{ background: '#0EA5E9', opacity: 0.7 }}
                  />
                )}
              </Link>
            )
          })}
        </div>
      </div>
    </nav>
  )
}

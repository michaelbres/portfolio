// /home/user/portfolio/frontend/src/components/Navbar.jsx
import { Link, useLocation } from 'react-router-dom'

const LINKS = [
  { to: '/',                        label: 'Home' },
  { to: '/sports',                  label: 'Sports Analytics' },
  { to: '/sports/mlb/fair-value',   label: 'Fair Value' },
  { to: '/sports/mlb/hr-fair-value', label: 'HR Props' },
  { to: '/sports/mlb/stuff-plus',   label: 'Stuff+' },
  { to: '/betting',                 label: 'Betting' },
]

export default function Navbar() {
  const { pathname } = useLocation()

  return (
    <nav
      className="sticky top-0 z-50"
      style={{
        // Apple-style light frosted glass
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        backgroundColor: 'rgba(255, 255, 255, 0.82)',
        borderBottom: '1px solid rgba(0, 0, 0, 0.08)',
      }}
    >
      <div className="max-w-5xl mx-auto px-6 flex items-center gap-8 h-12">

        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 shrink-0 group">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs tracking-tight"
            style={{
              background: 'linear-gradient(135deg, #0066CC, #2563EB)',
              color: '#fff',
              boxShadow: '0 1px 4px rgba(0,102,204,0.25)',
            }}
          >
            MB
          </div>
          <span
            className="text-snow font-semibold text-sm tracking-tight hidden sm:block"
            style={{ letterSpacing: '-0.01em' }}
          >
            Breslow Analytics
          </span>
        </Link>

        {/* Nav links */}
        <div className="flex items-center gap-0.5 ml-auto">
          {LINKS.map(({ to, label }) => {
            const active =
              to === '/'
                ? pathname === '/'
                : pathname === to || pathname.startsWith(to + '/')

            return (
              <Link
                key={to}
                to={to}
                className={[
                  'relative px-3.5 py-1.5 text-sm rounded-full transition-all duration-200',
                  active
                    ? 'text-electric font-medium'
                    : 'text-mist hover:text-snow',
                ].join(' ')}
                style={{
                  backgroundColor: active ? 'rgba(0, 102, 204, 0.08)' : undefined,
                  letterSpacing: '-0.01em',
                }}
              >
                {label}
              </Link>
            )
          })}
        </div>
      </div>
    </nav>
  )
}

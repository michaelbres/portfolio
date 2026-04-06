// /home/user/portfolio/frontend/src/pages/sports/SportsAnalytics.jsx
import { Link } from 'react-router-dom'
import Navbar from '../../components/Navbar'

const SPORTS = [
  {
    to: '/sports/mlb',
    sport: 'MLB',
    title: 'Baseball Analytics',
    description:
      'Statcast pitch-by-pitch data. Leaderboards, movement profiles, pitch location charts, and your own Stuff+ model.',
    accent: '#0EA5E9',
    accentBg: 'rgba(14,165,233,0.10)',
    accentBorder: 'rgba(14,165,233,0.20)',
    available: true,
    subLinks: [
      { to: '/sports/mlb', label: 'Pitch Dashboard' },
      { to: '/sports/mlb/fair-value', label: 'Fair Value Model' },
    ],
  },
  {
    to: '#',
    sport: 'NFL',
    title: 'Football Analytics',
    description: 'Coming soon — play-by-play data, EPA models, and route charting.',
    accent: '#86868B',
    accentBg: 'rgba(134,134,139,0.08)',
    accentBorder: 'rgba(134,134,139,0.15)',
    available: false,
  },
  {
    to: '#',
    sport: 'NBA',
    title: 'Basketball Analytics',
    description: 'Coming soon — shot charts, on/off splits, and player tracking.',
    accent: '#86868B',
    accentBg: 'rgba(134,134,139,0.08)',
    accentBorder: 'rgba(134,134,139,0.15)',
    available: false,
  },
]

export default function SportsAnalytics() {
  return (
    <div className="mesh-bg min-h-screen">
      <Navbar />

      <div className="max-w-5xl mx-auto px-5 py-16">
        {/* Header */}
        <div className="mb-12">
          <p className="text-xs font-semibold tracking-widest uppercase text-mist mb-3">
            Portfolio
          </p>
          <h1
            className="text-snow font-display leading-none tracking-tight"
            style={{ fontSize: 'clamp(2rem, 6vw, 4rem)', fontWeight: 300 }}
          >
            Sports Analytics
          </h1>
        </div>

        {/* Sport cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {SPORTS.map((s) => {
            const Wrapper = s.available ? Link : 'div'
            return (
              <Wrapper
                key={s.sport}
                to={s.available ? s.to : undefined}
                className={[
                  'bento-tile flex flex-col p-5',
                  !s.available ? 'opacity-50 cursor-default' : '',
                ].join(' ')}
                style={{ textDecoration: 'none' }}
              >
                {/* Sport badge */}
                <div className="mb-4">
                  <span
                    className="inline-block text-xs font-semibold tracking-widest uppercase px-2.5 py-1 rounded-full"
                    style={{
                      background: s.accentBg,
                      border: `1px solid ${s.accentBorder}`,
                      color: s.accent,
                    }}
                  >
                    {s.sport}
                  </span>
                </div>

                <h2 className="text-snow text-lg font-semibold leading-tight mb-2">
                  {s.title}
                </h2>
                <p className="text-mist text-sm leading-relaxed flex-1">
                  {s.description}
                </p>

                {/* Sub-links or CTA */}
                {s.available && s.subLinks ? (
                  <div className="mt-5 flex flex-col gap-1.5">
                    {s.subLinks.map((sl) => (
                      <Link
                        key={sl.to}
                        to={sl.to}
                        className="text-xs font-medium transition-colors duration-150"
                        style={{ color: s.accent, textDecoration: 'none' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {sl.label} →
                      </Link>
                    ))}
                  </div>
                ) : s.available ? (
                  <div className="mt-5">
                    <span
                      className="text-xs font-medium"
                      style={{ color: s.accent }}
                    >
                      View Data →
                    </span>
                  </div>
                ) : (
                  <div className="mt-5">
                    <span className="text-xs text-mist">In development</span>
                  </div>
                )}
              </Wrapper>
            )
          })}
        </div>
      </div>
    </div>
  )
}

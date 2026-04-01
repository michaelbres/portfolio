import { Link } from 'react-router-dom'
import Navbar from '../../components/Navbar'

const SPORTS = [
  {
    to: '/sports/mlb',
    sport: 'MLB',
    title: 'Baseball Analytics',
    description: 'Statcast pitch-by-pitch data. Leaderboards, movement profiles, pitch location charts, and your own Stuff+ model.',
    color: 'bg-sv-red',
    icon: '⚾',
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
    color: 'bg-pop-blue',
    icon: '🏈',
    available: false,
  },
  {
    to: '#',
    sport: 'NBA',
    title: 'Basketball Analytics',
    description: 'Coming soon — shot charts, on/off splits, and player tracking.',
    color: 'bg-pop-yellow',
    icon: '🏀',
    available: false,
  },
]

export default function SportsAnalytics() {
  return (
    <div className="min-h-screen bg-sv-light">
      <Navbar />

      <div className="max-w-6xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="mb-10">
          <div className="bg-sv-red text-white border-4 border-black inline-block px-5 py-2 mb-4"
               style={{ boxShadow: '4px 4px 0 #000' }}>
            <span className="font-bangers text-2xl tracking-widest">SPORTS ANALYTICS</span>
          </div>
          <h1 className="font-bangers text-6xl text-black"
              style={{ textShadow: '4px 4px 0 #C8102E' }}>
            CHOOSE A SPORT
          </h1>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {SPORTS.map((s) => {
            const Wrapper = s.available ? Link : 'div'
            return (
              <Wrapper
                key={s.sport}
                to={s.available ? s.to : undefined}
                className={`comic-card overflow-hidden ${!s.available ? 'opacity-60 cursor-default' : ''}`}
              >
                <div className={`${s.color} border-b-4 border-black px-6 py-6`}>
                  <div className="text-5xl mb-3">{s.icon}</div>
                  <div className="font-bangers text-4xl text-white tracking-wider leading-none">
                    {s.sport}
                  </div>
                  <div className="font-sans text-white text-sm opacity-80 mt-1">{s.title}</div>
                </div>
                <div className="bg-white px-6 py-5">
                  <p className="text-gray-700 text-sm font-sans leading-relaxed">{s.description}</p>
                  {s.available && s.subLinks ? (
                    <div className="mt-4 flex flex-col gap-1">
                      {s.subLinks.map((sl) => (
                        <Link
                          key={sl.to}
                          to={sl.to}
                          className="font-bangers text-sm tracking-widest text-sv-red border-b-2 border-sv-red w-fit"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {sl.label} →
                        </Link>
                      ))}
                    </div>
                  ) : s.available && (
                    <div className="mt-4">
                      <span className="font-bangers text-sm tracking-widest text-sv-red border-b-2 border-sv-red">
                        View Data →
                      </span>
                    </div>
                  )}
                </div>
              </Wrapper>
            )
          })}
        </div>
      </div>
    </div>
  )
}

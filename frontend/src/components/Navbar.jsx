import { Link, useLocation } from 'react-router-dom'

const LINKS = [
  { to: '/',       label: 'Home' },
  { to: '/sports', label: 'Sports Analytics' },
]

export default function Navbar() {
  const { pathname } = useLocation()

  return (
    <nav className="bg-black text-white border-b-4 border-pop-yellow sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-8 h-14">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <div className="w-8 h-8 bg-pop-yellow border-2 border-white flex items-center justify-center">
            <span className="font-bangers text-black text-sm leading-none">MB</span>
          </div>
          <span className="font-bangers text-pop-yellow tracking-widest text-lg hidden sm:block">
            MICHAEL BRESLOW
          </span>
        </Link>

        <div className="flex gap-1 ml-4">
          {LINKS.map(({ to, label }) => {
            const active = pathname === to || (to !== '/' && pathname.startsWith(to))
            return (
              <Link
                key={to}
                to={to}
                className={`px-4 py-1 font-bangers tracking-wider text-sm uppercase border-2 transition-colors ${
                  active
                    ? 'bg-pop-yellow text-black border-pop-yellow'
                    : 'border-transparent hover:border-pop-yellow hover:text-pop-yellow'
                }`}
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

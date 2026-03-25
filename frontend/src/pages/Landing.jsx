import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'

const PROJECTS = [
  {
    to: '/sports',
    title: 'Sports Analytics',
    subtitle: 'MLB · Statcast · Pitch Data',
    description:
      'Baseball Savant-style pitch analytics. Search every pitch from the 2025 season, explore pitcher arsenals, and build Stuff+ models.',
    color: 'bg-sv-red',
    textColor: 'text-white',
    accentColor: 'bg-pop-yellow',
    emoji: '⚾',
    tag: 'LIVE',
  },
  {
    to: '#',
    title: 'Coming Soon',
    subtitle: 'More projects on the way',
    description: 'Check back for new analytics projects covering football, basketball, finance, and more.',
    color: 'bg-pop-blue',
    textColor: 'text-white',
    accentColor: 'bg-pop-yellow',
    emoji: '🔮',
    tag: 'SOON',
  },
]

export default function Landing() {
  return (
    <div className="min-h-screen bg-white">
      <Navbar />

      {/* Hero */}
      <header className="halftone-bg border-b-4 border-black overflow-hidden">
        <div className="max-w-7xl mx-auto px-6 py-20 flex flex-col items-start gap-6">
          {/* ZAPP! label */}
          <div className="bg-pop-yellow border-4 border-black px-4 py-1 inline-block"
               style={{ boxShadow: '4px 4px 0 #000', transform: 'rotate(-1deg)' }}>
            <span className="font-bangers text-black text-2xl tracking-widest">ANALYTICS PORTFOLIO</span>
          </div>

          {/* Name */}
          <h1
            className="font-bangers text-black leading-none"
            style={{
              fontSize: 'clamp(4rem, 12vw, 10rem)',
              letterSpacing: '0.04em',
              WebkitTextStroke: '3px #000',
              textShadow: '6px 6px 0 #FF2D2D',
            }}
          >
            MICHAEL
            <br />
            BRESLOW
          </h1>

          {/* Tagline bubble */}
          <div className="relative bg-white border-4 border-black px-6 py-3 max-w-xl"
               style={{ boxShadow: '5px 5px 0 #000' }}>
            {/* Speech bubble tail */}
            <div className="absolute -bottom-5 left-10 w-0 h-0"
                 style={{
                   borderLeft: '12px solid transparent',
                   borderRight: '12px solid transparent',
                   borderTop: '20px solid #000',
                 }} />
            <div className="absolute -bottom-3 left-11 w-0 h-0"
                 style={{
                   borderLeft: '10px solid transparent',
                   borderRight: '10px solid transparent',
                   borderTop: '18px solid #fff',
                 }} />
            <p className="font-sans text-lg font-semibold text-gray-800">
              Turning raw data into insights — one pitch at a time.
            </p>
          </div>
        </div>
      </header>

      {/* Projects */}
      <main className="max-w-7xl mx-auto px-6 py-16">
        <div className="flex items-center gap-4 mb-10">
          <h2 className="font-bangers text-5xl tracking-wider"
              style={{ textShadow: '3px 3px 0 #0055FF' }}>
            PROJECTS
          </h2>
          <div className="flex-1 border-t-4 border-black" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {PROJECTS.map((p) => (
            <ProjectCard key={p.title} {...p} />
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t-4 border-black bg-black text-white py-8 px-6 text-center">
        <span className="font-bangers text-pop-yellow tracking-widest text-lg">
          MICHAEL BRESLOW
        </span>
        <span className="mx-3 text-gray-500">·</span>
        <a
          href="https://github.com/michaelbres"
          target="_blank"
          rel="noopener noreferrer"
          className="text-gray-300 hover:text-pop-yellow transition-colors font-sans text-sm"
        >
          github.com/michaelbres
        </a>
      </footer>
    </div>
  )
}

function ProjectCard({ to, title, subtitle, description, color, textColor, accentColor, emoji, tag }) {
  const isDisabled = to === '#'
  const Wrapper = isDisabled ? 'div' : Link

  return (
    <Wrapper
      to={isDisabled ? undefined : to}
      className={`comic-card block overflow-hidden ${isDisabled ? 'opacity-70 cursor-default' : ''}`}
    >
      {/* Card header */}
      <div className={`${color} ${textColor} px-6 py-5 border-b-4 border-black`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="text-4xl">{emoji}</span>
              <div className={`${accentColor} text-black text-xs font-bangens font-bold px-2 py-0.5 border-2 border-black`}>
                {tag}
              </div>
            </div>
            <h3 className="font-bangers text-3xl tracking-wider leading-none mt-2">{title}</h3>
            <p className="text-sm opacity-80 mt-1 font-sans">{subtitle}</p>
          </div>
          {!isDisabled && (
            <div className="text-3xl font-bangers mt-2 opacity-60">→</div>
          )}
        </div>
      </div>

      {/* Card body */}
      <div className="px-6 py-5 bg-white">
        <p className="text-gray-700 font-sans text-sm leading-relaxed">{description}</p>
        {!isDisabled && (
          <div className="mt-4">
            <span className="font-bangers text-sm tracking-widest text-sv-red uppercase border-b-2 border-sv-red">
              Explore →
            </span>
          </div>
        )}
      </div>
    </Wrapper>
  )
}

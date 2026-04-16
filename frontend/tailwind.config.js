// /home/user/portfolio/frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── Legacy pop-art palette (kept for backward compat) ─────────────────
        'pop-red':    '#FF2D2D',
        'pop-blue':   '#0055FF',
        'pop-yellow': '#FFE600',
        'pop-cyan':   '#00DDFF',
        // ── Baseball Savant palette ───────────────────────────────────────────
        'sv-red':     '#C8102E',
        'sv-blue':    '#003087',
        'sv-light':   '#F4F4F4',
        'sv-dark':    '#1A1A2E',
        'sv-mid':     '#5B6770',
        // ── Apple Design Language palette ─────────────────────────────────────
        // Remapped from dark-mode to light-mode semantics.
        // All Tailwind classes (text-snow, bg-surface, etc.) auto-update.
        'void':       '#F5F5F7',   // page background — Apple off-white
        'surface':    '#FFFFFF',   // card/tile background — pure white
        'surface-2':  '#F5F5F7',   // table headers, secondary surfaces
        'surface-3':  '#E8E8ED',   // hover states
        'snow':       '#1D1D1F',   // primary text — Apple jet black
        'mist':       '#86868B',   // secondary text — unchanged, works both modes
        'smoke':      '#D2D2D7',   // borders/dividers — light gray
        'electric':   '#0066CC',   // Apple Blue (interactive elements only)
        'emerald':    '#28CD41',   // Apple Green
        'amethyst':   '#A855F7',   // Amethyst (tertiary)
      },
      fontFamily: {
        // Legacy (kept for any inner pages still using it)
        bangers: ['Bangers', 'cursive'],
        // Renders as SF Pro on Apple devices, Inter everywhere else
        display: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"SF Pro Display"',
          'Inter',
          'system-ui',
          'sans-serif',
        ],
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"SF Pro Text"',
          'Inter',
          'system-ui',
          'sans-serif',
        ],
      },
      boxShadow: {
        // Legacy comic shadows (kept for backward compat)
        comic:      '4px 4px 0 #000',
        'comic-lg': '6px 6px 0 #000',
        'comic-xl': '8px 8px 0 #000',
        // Light-mode card shadows — soft, layered
        tile:         '0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)',
        'tile-hover': '0 8px 28px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.05)',
        'tile-sm':    '0 1px 3px rgba(0,0,0,0.06)',
        glow:         '0 0 24px rgba(0,102,204,0.12)',
        'glow-emerald':   '0 0 24px rgba(40,205,65,0.12)',
        'glow-amethyst':  '0 0 24px rgba(168,85,247,0.10)',
      },
      backgroundImage: {
        halftone: "radial-gradient(circle, #00000010 1px, transparent 1px)",
      },
      backgroundSize: {
        halftone: '20px 20px',
      },
      borderColor: {
        // Light-mode border tokens
        'black-6':  'rgba(0,0,0,0.06)',
        'black-8':  'rgba(0,0,0,0.08)',
        'black-12': 'rgba(0,0,0,0.12)',
        // Legacy dark-mode tokens (kept so old classes don't break)
        'white-8':  'rgba(255,255,255,0.08)',
        'white-12': 'rgba(255,255,255,0.12)',
        'white-20': 'rgba(255,255,255,0.20)',
      },
      borderRadius: {
        // Squircle-adjacent: Apple uses ~20-28px continuous curvature
        'apple': '22px',
        'apple-lg': '28px',
      },
      animation: {
        'mesh-shift': 'meshShift 24s ease-in-out infinite alternate',
        'pulse-slow':  'pulse 4s cubic-bezier(0.4,0,0.6,1) infinite',
        'float':       'float 6s ease-in-out infinite',
      },
      keyframes: {
        meshShift: {
          '0%':   { backgroundPosition: '0% 50%' },
          '100%': { backgroundPosition: '100% 50%' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':      { transform: 'translateY(-8px)' },
        },
      },
    },
  },
  plugins: [],
}

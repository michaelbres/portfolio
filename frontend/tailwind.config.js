// /home/user/portfolio/frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── Legacy pop-art palette (kept for backward compat on inner pages) ──
        'pop-red':    '#FF2D2D',
        'pop-blue':   '#0055FF',
        'pop-yellow': '#FFE600',
        'pop-cyan':   '#00DDFF',
        // ── Baseball Savant palette ──
        'sv-red':     '#C8102E',
        'sv-blue':    '#003087',
        'sv-light':   '#F4F4F4',
        'sv-dark':    '#1A1A2E',
        'sv-mid':     '#5B6770',
        // ── Bento / dark-mode palette ──
        'void':       '#080808',
        'surface':    '#141414',
        'surface-2':  '#1C1C1E',
        'surface-3':  '#2C2C2E',
        'snow':       '#F5F5F7',
        'mist':       '#86868B',
        'smoke':      '#3A3A3C',
        'electric':   '#0EA5E9',
        'emerald':    '#10B981',
        'amethyst':   '#A855F7',
      },
      fontFamily: {
        // Legacy (kept for any inner pages still using it)
        bangers: ['Bangers', 'cursive'],
        // New display stack — renders as SF Pro on Apple, Inter everywhere else
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
        // New dark-mode shadows
        tile:       '0 1px 3px rgba(0,0,0,0.5), 0 4px 16px rgba(0,0,0,0.3)',
        'tile-hover': '0 4px 24px rgba(0,0,0,0.6), 0 8px 32px rgba(0,0,0,0.4)',
        'tile-sm':  '0 1px 3px rgba(0,0,0,0.5)',
        glow:       '0 0 20px rgba(14,165,233,0.25)',
        'glow-emerald': '0 0 20px rgba(16,185,129,0.25)',
        'glow-amethyst': '0 0 20px rgba(168,85,247,0.25)',
      },
      backgroundImage: {
        // Legacy halftone (kept for backward compat)
        halftone: "radial-gradient(circle, #00000018 1px, transparent 1px)",
      },
      backgroundSize: {
        halftone: '20px 20px',
      },
      borderColor: {
        'white-8':  'rgba(255,255,255,0.08)',
        'white-12': 'rgba(255,255,255,0.12)',
        'white-20': 'rgba(255,255,255,0.20)',
      },
      animation: {
        'mesh-shift': 'meshShift 18s ease-in-out infinite alternate',
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

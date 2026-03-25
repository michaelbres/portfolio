/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Pop art palette
        'pop-red':    '#FF2D2D',
        'pop-blue':   '#0055FF',
        'pop-yellow': '#FFE600',
        'pop-cyan':   '#00DDFF',
        // Baseball Savant palette
        'sv-red':     '#C8102E',
        'sv-blue':    '#003087',
        'sv-light':   '#F4F4F4',
        'sv-dark':    '#1A1A2E',
        'sv-mid':     '#5B6770',
      },
      fontFamily: {
        bangers: ['Bangers', 'cursive'],
        sans:    ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        comic:    '4px 4px 0 #000',
        'comic-lg': '6px 6px 0 #000',
        'comic-xl': '8px 8px 0 #000',
      },
      backgroundImage: {
        halftone: "radial-gradient(circle, #00000018 1px, transparent 1px)",
      },
      backgroundSize: {
        halftone: '20px 20px',
      },
    },
  },
  plugins: [],
}

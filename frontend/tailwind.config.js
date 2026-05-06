/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ub: {
          blue: '#003087',
          'blue-dark': '#001A4D',
          'blue-light': '#EBF3FF',
          red: '#C8102E',
          'red-light': '#FEE2E2',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui'],
        mono: ['"IBM Plex Mono"', 'ui-monospace'],
      },
      boxShadow: {
        glass: '0 1px 2px rgba(0, 48, 135, 0.04), 0 8px 24px rgba(0, 26, 77, 0.06)',
      },
    },
  },
  plugins: [],
}

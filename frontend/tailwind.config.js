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
        sans: ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui'],
        mono: ['"IBM Plex Mono"', 'ui-monospace'],
      },
    },
  },
  plugins: [],
}

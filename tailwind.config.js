/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx,js,jsx}'],
  theme: {
    extend: {
      colors: {
        night: {
          900: '#05070b',
          800: '#0a0f16',
          700: '#0f1622',
          600: '#131d2b'
        },
        neon: {
          cyan: '#3ef3ff',
          purple: '#8f6bff',
          mint: '#4dffb5'
        }
      },
      boxShadow: {
        glow: '0 0 32px rgba(62, 243, 255, 0.25)',
        glass: '0 20px 80px rgba(0, 0, 0, 0.45)'
      },
      backgroundImage: {
        'radial-glow': 'radial-gradient(circle at top, rgba(62, 243, 255, 0.18), transparent 55%)'
      }
    }
  },
  plugins: []
}

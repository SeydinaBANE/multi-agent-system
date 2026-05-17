import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#090c14',
        surface:  '#111827',
        surface2: '#1c2133',
        border:   '#1e2538',
        accent:   '#6366f1',
        success:  '#22c55e',
        error:    '#ef4444',
        muted:    '#64748b',
        text:     '#e2e8f0',
      },
      boxShadow: {
        'glow-accent': '0 0 20px rgba(99,102,241,0.18)',
        'glow-sm':     '0 0 10px rgba(99,102,241,0.12)',
        'glow-success':'0 0 8px rgba(34,197,94,0.35)',
      },
      animation: {
        'pulse-dot': 'pulse-dot 0.9s infinite',
        blink:       'blink 0.75s infinite',
        shimmer:     'shimmer 1.6s infinite',
      },
      keyframes: {
        'pulse-dot': { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.35' } },
        blink:       { '0%,100%': { opacity: '1' }, '50%': { opacity: '0' } },
        shimmer: {
          '0%':   { backgroundPosition: '-200% center' },
          '100%': { backgroundPosition: '200% center' },
        },
      },
    },
  },
  plugins: [],
}

export default config

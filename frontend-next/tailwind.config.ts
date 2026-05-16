import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#0f1117',
        surface:  '#1a1d27',
        surface2: '#21253a',
        border:   '#2a2d3d',
        accent:   '#6366f1',
        success:  '#22c55e',
        error:    '#ef4444',
        muted:    '#64748b',
        text:     '#e2e8f0',
      },
      animation: {
        'pulse-dot': 'pulse-dot 0.9s infinite',
        blink:       'blink 0.75s infinite',
      },
      keyframes: {
        'pulse-dot': { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.35' } },
        blink:       { '0%,100%': { opacity: '1' }, '50%': { opacity: '0' } },
      },
    },
  },
  plugins: [],
}

export default config

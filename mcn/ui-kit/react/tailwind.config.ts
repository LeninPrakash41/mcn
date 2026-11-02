import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        accent: {
          DEFAULT: '#3b82f6',
          hover: '#2563eb',
          bg: 'rgba(59, 130, 246, 0.08)',
        },
        surface: {
          DEFAULT: '#f4f4f5',
          2: '#e4e4e7',
        },
        muted: {
          DEFAULT: '#71717a',
          foreground: '#71717a',
        },
        mcn: {
          text: '#09090b',
          muted: '#71717a',
          border: '#d4d4d8',
          surface: '#f4f4f5',
          surface2: '#e4e4e7',
          accent: '#3b82f6',
          green: '#16a34a',
          red: '#dc2626',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      borderRadius: {
        sm: '4px',
        DEFAULT: '7px',
        md: '7px',
        lg: '10px',
        xl: '14px',
      },
    },
  },
  plugins: [],
}

export default config

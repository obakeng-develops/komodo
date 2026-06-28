/**
 * @type {import('tailwindcss').Config}
 */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  safelist: ['bg-success-500', 'bg-warning-500', 'bg-danger-500'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Helvetica Neue'", 'Arial', 'sans-serif'],
        serif: ['Georgia', "'Times New Roman'", 'serif'],
        mono: ["'JetBrains Mono'", 'monospace'],
      },
      colors: {
        // Greys
        surface: {
          50: '#fafafa',
          100: '#f5f5f5',
          200: '#eeeeee',
          300: '#e5e5e5',
          400: '#d4d4d4',
          500: '#a3a3a3',
          600: '#737373',
          700: '#525252',
          800: '#404040',
          900: '#262626',
          950: '#171717',
        },
        // Single accent
        accent: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
          950: '#1e1b4b',
        },
        // Semantic status colors (muted)
        success: {
          500: '#4ade80',
          600: '#22c55e',
        },
        warning: {
          500: '#fbbf24',
          600: '#d97706',
        },
        danger: {
          500: '#f87171',
          600: '#dc2626',
        },
      },
      borderRadius: {
        '2xl': '14px',
        '3xl': '18px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(0,0,0,.04), 0 12px 30px rgba(0,0,0,.04)',
        modal: '0 24px 64px rgba(0,0,0,.28)',
      },
      backgroundImage: {
        'stripe-pattern': 'repeating-linear-gradient(120deg, transparent, transparent 6px, currentColor 6px, currentColor 7px)',
      },
    },
  },
  plugins: [],
};

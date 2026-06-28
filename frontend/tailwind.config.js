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
      // Named type scale. Replaces the ~140 ad-hoc text-[NNpx] sizes; line-heights
      // follow the 1.3–1.5 body range. Display/title/heading are serif; the rest body/mono.
      fontSize: {
        micro: ['11px', { lineHeight: '1.45' }],
        label: ['13px', { lineHeight: '1.45' }],
        body: ['15px', { lineHeight: '1.5' }],
        heading: ['19px', { lineHeight: '1.3' }],
        title: ['28px', { lineHeight: '1.15', letterSpacing: '-0.01em' }],
        display: ['40px', { lineHeight: '1.05', letterSpacing: '-0.01em' }],
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
        // Semantic radii: controls (buttons/inputs/selects) and cards. The 2xl/3xl
        // aliases stay until screens migrate onto these.
        control: '8px',
        card: '14px',
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

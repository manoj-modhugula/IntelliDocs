import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-sans)', 'Plus Jakarta Sans', 'system-ui', 'sans-serif'],
        display: ['var(--font-display)', 'Fraunces', 'Georgia', 'serif'],
      },
      colors: {
        ink: 'var(--ink)',
        muted: 'var(--muted)',
        canvas: 'var(--bg)',
        accent: {
          DEFAULT: 'var(--accent)',
        },
      },
      borderRadius: {
        card: 'var(--radius)',
        field: 'var(--radius-sm)',
        pill: 'var(--radius-pill)',
      },
      transitionTimingFunction: {
        out: 'var(--ease-out)',
        spring: 'var(--ease-spring)',
        snap: 'var(--ease-snap)',
        leave: 'var(--ease-exit)',
      },
      transitionDuration: {
        color: 'var(--dur-color)',
        press: 'var(--dur-press)',
        hover: 'var(--dur-hover)',
        snap: 'var(--dur-snap)',
        enter: 'var(--dur-enter)',
        indicator: 'var(--dur-indicator)',
        overlay: 'var(--dur-overlay)',
        leave: 'var(--dur-exit)',
      },
    },
  },
  plugins: [],
};

export default config;

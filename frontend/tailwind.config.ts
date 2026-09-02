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
    },
  },
  plugins: [],
};

export default config;

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

interface ThemeState {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setPreference: (preference: ThemePreference) => void;
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === 'light' || preference === 'dark') return preference;
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function applyResolvedTheme(resolved: ResolvedTheme) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.dataset.theme = resolved;
  root.classList.toggle('dark', resolved === 'dark');
  root.style.colorScheme = resolved;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute('content', resolved === 'dark' ? '#0b0d12' : '#eef1f6');
  }
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      preference: 'system',
      resolved: 'light',
      setPreference: (preference) => {
        const resolved = resolveTheme(preference);
        applyResolvedTheme(resolved);
        set({ preference, resolved });
      },
    }),
    {
      name: 'intellidocs-theme',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ preference: state.preference }),
      merge: (persisted, current) => {
        const raw = (persisted ?? {}) as {
          preference?: ThemePreference;
          theme?: 'light' | 'dark';
        };
        const preference: ThemePreference =
          raw.preference === 'light' || raw.preference === 'dark' || raw.preference === 'system'
            ? raw.preference
            : raw.theme === 'light' || raw.theme === 'dark'
              ? raw.theme
              : current.preference;
        return { ...current, preference };
      },
      onRehydrateStorage: () => (state) => {
        if (!state) return;
        const resolved = resolveTheme(state.preference);
        applyResolvedTheme(resolved);
        state.resolved = resolved;
      },
    }
  )
);

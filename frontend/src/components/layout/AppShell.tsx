'use client';

import { usePathname, useRouter } from 'next/navigation';
import { memo, useState, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { Menu } from 'lucide-react';
import { useThemeStore, applyResolvedTheme, resolveTheme } from '@/store/themeStore';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { useAuthStore } from '@/store/authStore';
import { ConversationQuickSwitcher } from '@/components/chat/ConversationQuickSwitcher';

const TOKEN_REFRESH_MS = 50 * 60 * 1000;

const AUTH_PATHS = ['/login', '/register'];

const NAV_ROUTES = ['/', '/chat', '/documents', '/workspaces', '/settings'] as const;

function ThemeSync() {
  const preference = useThemeStore((s) => s.preference);

  useEffect(() => {
    const apply = () => {
      const resolved = resolveTheme(preference);
      applyResolvedTheme(resolved);
      useThemeStore.setState({ resolved });
    };
    apply();
    if (preference !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', apply);
    return () => mq.removeEventListener('change', apply);
  }, [preference]);

  return null;
}

export const AppShell = memo(function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [quickSwitcherOpen, setQuickSwitcherOpen] = useState(false);
  const isAuthPage = AUTH_PATHS.includes(pathname ?? '');
  const { cachedWorkspaces, setSelectedWorkspaceId } = useWorkspaceStore();
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (!token) return;
    const id = window.setInterval(() => {
      void useAuthStore.getState().refreshToken();
    }, TOKEN_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [token]);

  useEffect(() => {
    if (isAuthPage) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      const target = e.target as HTMLElement;
      const inInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable;
      const isNumKey = e.key >= '1' && e.key <= '9';
      if (!mod) return;
      if (inInput && !(isNumKey || e.key.toLowerCase() === 'o')) return;

      const num = e.key === '1' ? 1 : e.key === '2' ? 2 : e.key === '3' ? 3 : e.key === '4' ? 4 : e.key === '5' ? 5 : 0;
      if (num >= 1 && num <= 5 && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        const route = NAV_ROUTES[num - 1];
        if (route && pathname !== route) router.push(route);
        return;
      }

      if (e.shiftKey && mod && isNumKey) {
        const wsNum = e.key === '1' ? 1 : e.key === '2' ? 2 : e.key === '3' ? 3 : e.key === '4' ? 4 : e.key === '5' ? 5 : e.key === '6' ? 6 : e.key === '7' ? 7 : e.key === '8' ? 8 : e.key === '9' ? 9 : 0;
        if (wsNum >= 1 && wsNum <= 9 && cachedWorkspaces.length >= wsNum) {
          e.preventDefault();
          const workspace = cachedWorkspaces[wsNum - 1];
          if (workspace) {
            setSelectedWorkspaceId(workspace.id);
            if (pathname !== '/chat') router.push('/chat');
          }
        }
        return;
      }

      if (mod && e.key.toLowerCase() === 'o') {
        e.preventDefault();
        setQuickSwitcherOpen((open) => !open);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isAuthPage, pathname, router, cachedWorkspaces, setSelectedWorkspaceId]);

  if (isAuthPage) {
    return (
      <div className="flex min-h-screen overflow-hidden">
        <ThemeSync />
        <main id="main-content" className="flex-1 overflow-auto min-h-0" role="main">
          {children}
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden min-h-0">
      <ThemeSync />
      <ConversationQuickSwitcher
        open={quickSwitcherOpen}
        onClose={() => setQuickSwitcherOpen(false)}
      />
      <Sidebar
        isMobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />
      <main
        id="main-content"
        className="flex-1 flex flex-col overflow-hidden min-w-0 min-h-0"
        role="main"
      >
        <div className="lg:hidden flex-shrink-0 flex items-center gap-3 px-4 py-3 glass">
          <button
            type="button"
            onClick={() => setMobileSidebarOpen(true)}
            aria-label="Open menu"
            className="icon-btn"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="brand-wordmark">IntelliDocs</span>
        </div>
        <div className="flex-1 overflow-hidden flex flex-col min-h-0 min-w-0">
          {children}
        </div>
      </main>
    </div>
  );
});

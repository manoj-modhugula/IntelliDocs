'use client';

import { useState, memo, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  MessageSquare,
  FileText,
  Home,
  Plus,
  Sparkles,
  Trash2,
  Settings,
  LogIn,
  LogOut,
  User,
  X,
  FolderOpen,
} from 'lucide-react';
import { useChatStore } from '@/store/chatStore';
import { useAuthStore } from '@/store/authStore';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { useDocumentStore } from '@/store/documentStore';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', icon: Home, label: 'Home' },
  { href: '/chat', icon: MessageSquare, label: 'Chat' },
  { href: '/documents', icon: FileText, label: 'Documents' },
  { href: '/workspaces', icon: FolderOpen, label: 'Workspaces' },
  { href: '/settings', icon: Settings, label: 'Settings' },
];

const NAV_BASE = 'nav-item';

export const Sidebar = memo(function Sidebar({
  isMobileOpen,
  onMobileClose,
}: {
  isMobileOpen?: boolean;
  onMobileClose?: () => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const {
    conversations,
    getCurrentConversationId,
    createConversation,
    deleteConversation,
    setCurrentConversation,
  } = useChatStore();
  const { selectedWorkspaceId, clearOnLogout: clearWorkspace } = useWorkspaceStore();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const token = useAuthStore((s) => s.token);
  const authReady = useAuthStore((s) => s.hasHydrated);
  const isAuthenticated = authReady && Boolean(token);
  const clearDocument = useDocumentStore((s) => s.clearOnLogout);
  const clearChat = useChatStore((s) => s.clearOnLogout);

  const workspaceKey = selectedWorkspaceId ?? '';
  const recentConversations = conversations
    .filter((c) => (c.workspaceId ?? '') === workspaceKey)
    .slice(0, 5);
  const currentConversationId = getCurrentConversationId(workspaceKey);

  const handleNewChat = () => {
    createConversation(workspaceKey);
    router.push('/chat');
    onMobileClose?.();
  };

  const handleLogout = () => {
    logout();
    clearDocument();
    clearChat();
    clearWorkspace();
    router.push('/');
    onMobileClose?.();
  };

  const handleNavClick = () => {
    onMobileClose?.();
  };

  useEffect(() => {
    if (!isAuthenticated || !token) return;
    const prefetchRoutes = () => {
      ['/chat', '/documents', '/workspaces', '/settings'].forEach((href) => {
        router.prefetch(href);
      });
    };
    if (typeof requestIdleCallback !== 'undefined') {
      requestIdleCallback(prefetchRoutes, { timeout: 500 });
    } else {
      setTimeout(prefetchRoutes, 100);
    }
  }, [isAuthenticated, token, router]);

  const renderSidebarContent = (expanded: boolean) => (
    <>
      {/* Logo */}
      <div className="p-3 flex-shrink-0">
        <Link
          href="/"
          onClick={handleNavClick}
          className={cn(NAV_BASE, expanded ? 'px-3' : 'justify-center px-0')}
          aria-label="IntelliDocs home"
        >
          <span className="logo-mark !h-9 !w-9">
            <Sparkles className="w-4 h-4" />
          </span>
          {expanded && <span className="brand-wordmark truncate">IntelliDocs</span>}
        </Link>
      </div>

      {/* New Chat */}
      <div className="px-2 flex-shrink-0">
        <button
          type="button"
          onClick={handleNewChat}
          aria-label="Start new chat"
          className={cn(
            NAV_BASE,
            'w-full',
            expanded ? 'px-3' : 'justify-center px-0'
          )}
        >
          <Plus className="w-4 h-4 flex-shrink-0" />
          {expanded && <span>New Chat</span>}
        </button>
      </div>

      {/* Nav items */}
      <nav aria-label="Primary" className="px-2 pt-1 space-y-0.5 flex-shrink-0">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== '/' && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              prefetch={true}
              onClick={handleNavClick}
              aria-current={isActive ? 'page' : undefined}
              title={!expanded ? item.label : undefined}
              data-active={isActive}
              className={cn(
                NAV_BASE,
                expanded ? 'px-3' : 'justify-center px-0'
              )}
            >
              <item.icon className="w-4 h-4 flex-shrink-0" />
              {expanded && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Recent conversations (expanded only) */}
      {expanded && recentConversations.length > 0 && (
        <div className="flex-1 overflow-hidden px-2 pt-4 min-h-0">
          <p className="section-title px-3 mb-2">Recent</p>
          <div className="space-y-0.5 overflow-y-auto max-h-[180px]">
            {recentConversations.map((conv) => (
              <ConversationItem
                key={conv.id}
                id={conv.id}
                title={conv.title}
                isActive={currentConversationId === conv.id}
                onClick={() => {
                  setCurrentConversation(conv.id, workspaceKey);
                  router.push('/chat');
                  onMobileClose?.();
                }}
                onDelete={() => deleteConversation(conv.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Bottom: user + sign out */}
      <div className="px-2 mt-auto pt-2 pb-3 space-y-1">
        {isAuthenticated && user && expanded && (
          <div className="px-3 py-2.5 rounded-[14px] glass">
            <div className="flex items-center gap-2.5">
              <span className="logo-mark !h-8 !w-8">
                <User className="w-4 h-4" />
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-ink truncate">
                  {user.name || user.email.split('@')[0]}
                </p>
                <p className="text-[11px] text-muted truncate">{user.email}</p>
              </div>
            </div>
          </div>
        )}

        {!authReady ? (
          <div className="w-full h-10 rounded-xl glass opacity-40" aria-hidden="true" />
        ) : isAuthenticated ? (
          <button
            type="button"
            onClick={handleLogout}
            aria-label="Sign out"
            title={expanded ? undefined : 'Sign out'}
            className={cn(
              NAV_BASE,
              'w-full',
              expanded ? 'px-3' : 'justify-center px-0 min-h-[2.75rem]'
            )}
          >
            {expanded ? (
              <LogOut className="w-4 h-4 flex-shrink-0" />
            ) : (
              <span
                className="logo-mark !h-10 !w-10 text-sm font-semibold"
                aria-hidden
              >
                {(user?.name?.[0] || user?.email?.[0] || '?').toUpperCase()}
              </span>
            )}
            {expanded && <span>Sign out</span>}
          </button>
        ) : (
          <Link
            href="/login"
            onClick={handleNavClick}
            aria-label="Sign in"
            title={expanded ? undefined : 'Sign in'}
            className={cn(
              NAV_BASE,
              'w-full',
              expanded ? 'px-3' : 'justify-center px-0'
            )}
          >
            <LogIn className="w-4 h-4 flex-shrink-0" />
            {expanded && <span>Sign in</span>}
          </Link>
        )}
      </div>
    </>
  );

  return (
    <>
      {/* Desktop rail - expands on hover */}
      <aside
        aria-label="Main navigation"
        onMouseEnter={() => setIsExpanded(true)}
        onMouseLeave={() => setIsExpanded(false)}
        className={cn(
          'h-screen flex flex-col relative z-20 flex-shrink-0 sidebar-chrome',
          'will-change-[width] transition-[width] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)]',
          'rounded-r-[22px] mr-2',
          'hidden lg:flex',
          isExpanded ? 'w-56' : 'w-[4.25rem]'
        )}
      >
        {renderSidebarContent(isExpanded)}
      </aside>

      {/* Mobile backdrop */}
      <div
        aria-hidden
        onClick={onMobileClose}
        className={cn(
          'fixed inset-0 z-40 lg:hidden',
          'bg-[rgba(15,23,42,0.28)] backdrop-blur-sm',
          'transition-opacity duration-200',
          isMobileOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
      />

      {/* Mobile drawer */}
      <aside
        aria-label="Main navigation"
        className={cn(
          'fixed top-0 left-0 h-full w-72 max-w-[85vw] flex flex-col z-50 sidebar-chrome',
          'transition-transform duration-200 ease-[cubic-bezier(0.22,1,0.36,1)]',
          'lg:hidden',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex items-center justify-between p-3 flex-shrink-0">
          <span className="brand-wordmark">Menu</span>
          <button
            type="button"
            onClick={onMobileClose}
            aria-label="Close menu"
            className="icon-btn"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto flex flex-col min-h-0">
          {renderSidebarContent(!!isMobileOpen)}
        </div>
      </aside>
    </>
  );
});

interface ConversationItemProps {
  id: string;
  title: string;
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
}

const ConversationItem = memo(function ConversationItem({
  title,
  isActive,
  onClick,
  onDelete,
}: ConversationItemProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onClick()}
      data-active={isActive}
      className="nav-item group w-full cursor-pointer"
      onClick={onClick}
    >
      <MessageSquare className="w-4 h-4 flex-shrink-0" aria-hidden />
      <span className="truncate flex-1">{title || 'New Chat'}</span>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        aria-label={`Delete chat ${title || 'New Chat'}`}
        className="opacity-0 group-hover:opacity-100 p-1 rounded-lg text-muted hover:text-ink"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
});

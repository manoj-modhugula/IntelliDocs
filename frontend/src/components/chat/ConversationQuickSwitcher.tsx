'use client';

import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Search, MessageSquare, X } from 'lucide-react';
import { useChatStore } from '@/store/chatStore';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';

interface ConversationQuickSwitcherProps {
  open: boolean;
  onClose: () => void;
}

function formatConvDate(updatedAt: Date | string): string {
  try {
    const d = typeof updatedAt === 'string' ? new Date(updatedAt) : updatedAt;
    if (Number.isNaN(d.getTime())) return '';
    return format(d, 'MMM d');
  } catch {
    return '';
  }
}

export function ConversationQuickSwitcher({ open, onClose }: ConversationQuickSwitcherProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);

  const { conversations, getCurrentConversationId, setCurrentConversation } = useChatStore();
  const { selectedWorkspaceId } = useWorkspaceStore();
  const workspaceKey = selectedWorkspaceId ?? '';

  const conversationsInWorkspace = useMemo(
    () =>
      [...conversations]
        .filter((c) => (c.workspaceId ?? '') === workspaceKey)
        .sort((a, b) => {
          const ta = typeof a.updatedAt === 'string' ? new Date(a.updatedAt).getTime() : a.updatedAt.getTime();
          const tb = typeof b.updatedAt === 'string' ? new Date(b.updatedAt).getTime() : b.updatedAt.getTime();
          return tb - ta;
        }),
    [conversations, workspaceKey]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversationsInWorkspace;
    return conversationsInWorkspace.filter(
      (c) =>
        (c.title || 'New Chat').toLowerCase().includes(q) ||
        c.messages.some(
          (m) => m.content && m.content.toLowerCase().includes(q)
        )
    );
  }, [conversationsInWorkspace, query]);

  const currentConversationId = getCurrentConversationId(workspaceKey);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setSelectedIndex(0);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  useEffect(() => {
    setSelectedIndex((i) => (i >= filtered.length ? Math.max(0, filtered.length - 1) : i));
  }, [filtered.length]);

  const handleSelect = useCallback(
    (convId: string) => {
      setCurrentConversation(convId, workspaceKey);
      onClose();
      router.push('/chat');
    },
    [workspaceKey, setCurrentConversation, onClose, router]
  );

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => (i + 1) % Math.max(1, filtered.length));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => (i - 1 + filtered.length) % Math.max(1, filtered.length));
        return;
      }
      if (e.key === 'Enter' && filtered[selectedIndex]) {
        e.preventDefault();
        handleSelect(filtered[selectedIndex].id);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, filtered, selectedIndex, handleSelect, onClose]);

  useEffect(() => {
    const selected = listRef.current?.querySelector('[data-selected="true"]');
    selected?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selectedIndex]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] px-4 bg-black/40 dark:bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Switch conversation"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-lg rounded-2xl glass shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-white/10 dark:border-white/5">
          <Search className="w-4 h-4 text-slate-500 dark:text-slate-400 flex-shrink-0" aria-hidden />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search conversations..."
            aria-label="Search conversations"
            className="flex-1 min-w-0 bg-transparent text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400 text-sm focus:outline-none py-1"
          />
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-black/5 dark:hover:bg-white/8 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div
          ref={listRef}
          className="max-h-[50vh] overflow-y-auto py-2"
          role="listbox"
          aria-label="Conversations"
        >
          {filtered.length === 0 ? (
            <p className="px-4 py-6 text-sm text-slate-600 dark:text-slate-400 text-center">
              {query.trim() ? 'No conversations match.' : 'No conversations yet.'}
            </p>
          ) : (
            filtered.map((conv, idx) => (
              <button
                key={conv.id}
                type="button"
                role="option"
                aria-selected={idx === selectedIndex}
                data-selected={idx === selectedIndex}
                onClick={() => handleSelect(conv.id)}
                className={cn(
                  'w-full text-left flex items-center gap-3 px-4 py-3 transition-colors',
                  idx === selectedIndex
                    ? 'bg-white/25 dark:bg-white/15 text-slate-900 dark:text-slate-100'
                    : 'text-slate-700 dark:text-slate-300 hover:bg-black/5 dark:hover:bg-white/8'
                )}
              >
                <MessageSquare className="w-4 h-4 flex-shrink-0 text-slate-500 dark:text-slate-400" aria-hidden />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{conv.title || 'New Chat'}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {formatConvDate(conv.updatedAt)}
                    {currentConversationId === conv.id && ' · Current'}
                  </p>
                </div>
              </button>
            ))
          )}
        </div>
        <p className="px-4 py-2 text-[11px] text-slate-500 dark:text-slate-400 border-t border-white/10 dark:border-white/5">
          ↑↓ to move · Enter to open · Esc to close
        </p>
      </div>
    </div>
  );
}

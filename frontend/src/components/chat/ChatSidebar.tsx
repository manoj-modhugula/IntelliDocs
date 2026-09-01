'use client';

import { useState, useRef, useEffect, memo, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquarePlus, FileText, Upload, Pin, PinOff, Trash2, Pin as PinIcon } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useChatStore, type Conversation } from '@/store/chatStore';
import { useDocumentStore } from '@/store/documentStore';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { useAuthStore } from '@/store/authStore';


interface ChatSidebarProps {
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  setSidebarOpen: (open: boolean) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  handleExpandSidebar: () => void;
  leftPanelView: 'chats' | 'documents';
  setLeftPanelView: (view: 'chats' | 'documents') => void;
  selectedDocumentId: string;
  setSelectedDocumentId: (id: string) => void;
  documentUploadInputRef: React.RefObject<HTMLInputElement>;
  handleAddDocumentClick: () => void;
  handleDocumentFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  isUploading: boolean;
  currentConversationId: string | null;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onAnimationDeleteComplete: (id: string) => void;
  onTogglePinConversation: (id: string) => void;
  conversationsSorted: ReturnType<typeof useChatStore.getState>['conversations'];
  currentWorkspaceKey: string;
}

function formatConvDate(updatedAt: Date | string): string {
  try {
    const d = typeof updatedAt === 'string' ? new Date(updatedAt) : updatedAt;
    if (Number.isNaN(d.getTime())) return '';
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(d);
  } catch {
    return '';
  }
}

function ConversationRow({
  conv,
  isActive,
  isPinned,
  onSelectConversation,
  onTogglePinConversation,
  onDelete,
}: {
  conv: Conversation;
  isActive: boolean;
  isPinned: boolean;
  onSelectConversation: (id: string) => void;
  onTogglePinConversation: (id: string) => void;
  onDelete: () => void;
}) {
  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: -10, scale: 0.98 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 24, scale: 0.94, height: 0, marginTop: 0, marginBottom: 0 }}
      transition={{ type: 'spring', stiffness: 420, damping: 34, mass: 0.8 }}
      className="group/list overflow-hidden"
    >
      <div
        className={cn(
          'conv-item glass-interactive flex items-center gap-2 rounded-xl px-3 py-2 min-h-[2.5rem] min-w-0',
          isActive
            ? 'glass text-slate-900 dark:text-slate-100'
            : 'text-slate-600 dark:text-slate-400'
        )}
      >
        {isPinned && (
          <PinIcon className="w-3.5 h-3.5 flex-shrink-0 text-sky-500 dark:text-sky-400" aria-hidden aria-label="Pinned" />
        )}
        <button
          type="button"
          onClick={() => onSelectConversation(conv.id)}
          className="flex-1 min-w-0 text-left truncate text-sm font-medium"
        >
          {conv.title || 'New Chat'}
        </button>
        <div className={cn('flex items-center gap-0.5 flex-shrink-0 transition-opacity', isPinned ? 'opacity-100 visible' : 'opacity-0 group-hover/list:opacity-100 group-hover/list:visible')}>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onTogglePinConversation(conv.id);
            }}
            className={cn(
              'icon-btn p-1 rounded-lg hover:bg-black/[0.05] dark:hover:bg-white/[0.08]',
              isPinned && 'text-sky-500 dark:text-sky-400'
            )}
            title={isPinned ? 'Unpin' : 'Pin'}
            aria-label={isPinned ? 'Unpin' : 'Pin'}
          >
            {isPinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="icon-btn p-1 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-500/10"
            title="Delete"
            aria-label="Delete"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </motion.li>
  );
}

export const ChatSidebar = memo(function ChatSidebar({
  sidebarOpen,
  sidebarCollapsed,
  setSidebarOpen,
  leftPanelView,
  setLeftPanelView,
  selectedDocumentId,
  setSelectedDocumentId,
  documentUploadInputRef,
  handleAddDocumentClick,
  handleDocumentFileChange,
  isUploading,
  currentConversationId,
  onNewChat,
  onSelectConversation,
  onAnimationDeleteComplete,
  onTogglePinConversation,
  conversationsSorted,
  currentWorkspaceKey,
}: ChatSidebarProps) {
  const leftPanelRef = useRef<HTMLElement | null>(null);
  const swipeAccumRef = useRef(0);
  const swipeResetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const deletingIdRef = useRef<string | null>(null);
  deletingIdRef.current = deletingId;

  const { documents } = useDocumentStore();
  const { selectedWorkspaceId } = useWorkspaceStore();
  const userWorkspaceId = useAuthStore((s) => s.user?.workspace_id ?? null);
  const effectiveWorkspaceId =
    selectedWorkspaceId && selectedWorkspaceId !== '' ? selectedWorkspaceId : userWorkspaceId;

  const readyDocuments = documents.filter(
    (d) =>
      d.status === 'ready' &&
      (!effectiveWorkspaceId || String(d.workspaceId ?? '') === String(effectiveWorkspaceId))
  );

  const SWIPE_THRESHOLD = 80;
  useEffect(() => {
    const panel = leftPanelRef.current;
    if (!panel) return;
    const onWheel = (e: WheelEvent) => {
      if (!panel.contains(e.target as Node)) return;
      const dx = e.deltaX;
      const dy = e.deltaY;
      if (Math.abs(dx) <= Math.abs(dy)) return;
      if (swipeResetTimerRef.current) {
        clearTimeout(swipeResetTimerRef.current);
        swipeResetTimerRef.current = null;
      }
      swipeAccumRef.current += dx;
      if (swipeAccumRef.current > SWIPE_THRESHOLD) {
        setLeftPanelView('documents');
        swipeAccumRef.current = 0;
      } else if (swipeAccumRef.current < -SWIPE_THRESHOLD) {
        setLeftPanelView('chats');
        swipeAccumRef.current = 0;
      }
      swipeResetTimerRef.current = setTimeout(() => {
        swipeAccumRef.current = 0;
        swipeResetTimerRef.current = null;
      }, 200);
    };
    panel.addEventListener('wheel', onWheel, { passive: true });
    return () => {
      panel.removeEventListener('wheel', onWheel);
      if (swipeResetTimerRef.current) clearTimeout(swipeResetTimerRef.current);
    };
  }, [setLeftPanelView]);

  const visibleConversations = useMemo(
    () => conversationsSorted.filter((conv) => conv.id !== deletingId),
    [conversationsSorted, deletingId]
  );

  return (
    <>
      <aside
        ref={leftPanelRef}
        className={cn(
          'flex-shrink-0 flex flex-col w-[240px] glass border-r border-white/20 dark:border-white/10',
          'transition-[width,min-width,opacity] duration-200 ease-out',
          'max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-40 max-md:transform max-md:transition-transform max-md:duration-200 max-md:ease-out',
          !sidebarOpen && 'max-md:translate-x-[-100%]',
          sidebarCollapsed && 'md:w-0 md:min-w-0 md:overflow-hidden md:border-0 md:opacity-0 md:pointer-events-none'
        )}
      >
        <div className="flex-shrink-0 pt-4 px-2 pb-2 border-b border-white/10 dark:border-white/5">
          <div
            role="tablist"
            aria-label="Chats or documents"
            className="flex rounded-xl p-0.5 glass"
          >
            <button
              type="button"
              role="tab"
              aria-selected={leftPanelView === 'chats'}
              onClick={() => setLeftPanelView('chats')}
              className={cn(
                'tab-btn flex-1 py-2 rounded-lg text-sm font-medium',
                leftPanelView === 'chats'
                  ? 'glass text-slate-900 dark:text-slate-100'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-black/[0.05] dark:hover:bg-white/[0.08]'
              )}
            >
              Chats
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={leftPanelView === 'documents'}
              onClick={() => setLeftPanelView('documents')}
              className={cn(
                'tab-btn flex-1 py-2 rounded-lg text-sm font-medium',
                leftPanelView === 'documents'
                  ? 'glass text-slate-900 dark:text-slate-100'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-black/[0.05] dark:hover:bg-white/[0.08]'
              )}
            >
              Docs
            </button>
          </div>
        </div>

        {leftPanelView === 'chats' ? (
          <>
            <div className="flex-shrink-0 p-2 border-b border-white/10 dark:border-white/5">
              <button
                type="button"
                onClick={onNewChat}
                className="glass-interactive w-full flex items-center justify-center gap-2 py-2 rounded-xl glass text-slate-900 dark:text-slate-100 text-sm font-medium hover:bg-black/[0.07] dark:hover:bg-white/[0.1]"
                aria-label="New conversation"
              >
                <MessageSquarePlus className="w-4 h-4" aria-hidden />
                New chat
              </button>
            </div>
            <div className="flex-1 overflow-y-auto min-h-0 py-2 px-2">
            <nav aria-label="Conversation list">
              {conversationsSorted.length === 0 ? (
                <div className="rounded-xl glass p-4 text-center">
                  <p className="text-sm text-slate-500 dark:text-slate-400">No chats yet</p>
                </div>
              ) : (
                <ul className="space-y-1">
                  <AnimatePresence
                    initial={false}
                    mode="popLayout"
                    onExitComplete={() => {
                      if (!deletingIdRef.current) return;
                      onAnimationDeleteComplete(deletingIdRef.current);
                      setDeletingId(null);
                    }}
                  >
                  {visibleConversations.map((conv) => {
                    const isPinned = conv.isPinned ?? false;
                    const isActive = currentConversationId === conv.id;
                    return (
                      <ConversationRow
                        key={conv.id}
                        conv={conv}
                        isActive={isActive}
                        isPinned={isPinned}
                        onSelectConversation={onSelectConversation}
                        onTogglePinConversation={onTogglePinConversation}
                        onDelete={() => { setDeletingId(conv.id); }}
                      />
                    );
                  })}
                  </AnimatePresence>
                </ul>
              )}
            </nav>
          </div>
          </>
        ) : (
          <>
            <input
              ref={documentUploadInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.txt,.md,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
              className="hidden"
              aria-hidden
              onChange={handleDocumentFileChange}
            />
            <div className="flex-shrink-0 p-2 border-b border-white/10 dark:border-white/5">
              <button
                type="button"
                onClick={handleAddDocumentClick}
                disabled={isUploading}
                className="glass-interactive w-full flex items-center justify-center gap-2 py-2 rounded-xl glass text-slate-900 dark:text-slate-100 text-sm font-medium hover:bg-black/[0.07] dark:hover:bg-white/[0.1] disabled:opacity-60 disabled:pointer-events-none"
                aria-label="Add document to workspace"
              >
                <Upload className="w-4 h-4" aria-hidden />
                {isUploading ? 'Uploading…' : 'Add document'}
              </button>
            </div>
            <div className="flex-1 overflow-y-auto min-h-0 py-2 px-2" aria-label="Documents">
              {readyDocuments.length === 0 ? (
                <div className="rounded-xl glass p-4 text-center">
                  <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">No documents here</p>
                  <Link
                    href="/documents"
                    className="text-sm text-sky-600 dark:text-sky-400 hover:underline"
                  >
                    Upload documents
                  </Link>
                </div>
              ) : (
                <ul className="space-y-1">
                  {readyDocuments.map((d) => {
                    const isSelected = selectedDocumentId === d.id;
                    return (
                      <li key={d.id}>
                        <button
                          type="button"
                          onClick={() => setSelectedDocumentId(isSelected ? '' : d.id)}
                          className={cn(
                            'doc-item w-full flex items-center gap-2 rounded-xl px-3 py-2 min-h-[2.25rem] text-left',
                            isSelected
                              ? 'glass text-slate-900 dark:text-slate-100'
                              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
                          )}
                        >
                          <FileText className="w-4 h-4 flex-shrink-0 text-slate-500 dark:text-slate-400" aria-hidden />
                          <span className="flex-1 min-w-0 text-sm font-medium truncate">
                            {d.name}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </>
        )}

      </aside>

      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close sidebar"
          className="md:hidden fixed inset-0 z-30 bg-black/40 backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </>
  );
});

'use client';

import { memo, useState, useRef, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Download, FileText, Braces } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import type { Conversation } from '@/store/chatStore';

interface ChatHeaderProps {
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  setSidebarOpen: (open: boolean) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  handleExpandSidebar: () => void;
  fullFocusMode: boolean;
  setFullFocusMode: (mode: boolean) => void;
  readyDocuments: { id: string; name: string }[];
  selectedDocumentId: string;
  setSelectedDocumentId: (id: string) => void;
  workspaces: { id: string; name: string }[];
  selectedWorkspaceId: string | null;
  setSelectedWorkspaceId: (id: string | null) => void;
  currentConversation: Conversation | null;
  onExportChat: (format?: 'markdown' | 'json') => void;
}

export const ChatHeader = memo(function ChatHeader({
  sidebarOpen,
  sidebarCollapsed,
  setSidebarOpen,
  handleExpandSidebar,
  fullFocusMode,
  setFullFocusMode,
  readyDocuments,
  selectedDocumentId,
  setSelectedDocumentId,
  workspaces,
  selectedWorkspaceId,
  setSelectedWorkspaceId,
  currentConversation,
  onExportChat,
}: ChatHeaderProps) {
  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setShowExportMenu(false);
      }
    };
    if (showExportMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showExportMenu]);

  return (
    <>
      {fullFocusMode && (
        <div className="md:flex hidden absolute top-2 right-2 z-20">
          <button
            type="button"
            onClick={() => {
              setFullFocusMode(false);
              try { window.localStorage.setItem('intellidocs-chat-full-focus', 'false'); } catch { /* ignore */ }
            }}
            className="glass-interactive px-3 py-1.5 rounded-lg glass text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-black/[0.07] dark:hover:bg-white/[0.1]"
            title="Exit full focus (⌘⇧K)"
          >
            Exit focus (⌘⇧K)
          </button>
        </div>
      )}

      {!fullFocusMode && (
        <div className="relative z-10 flex-shrink-0 border-b border-white/20 dark:border-white/10 px-4 sm:px-6 py-3 glass">
          <div className="max-w-4xl mx-auto flex items-center justify-between gap-4">
            {/* Left: sidebar toggle + title */}
            <div className="flex items-center gap-2 min-w-0">
              <button
                type="button"
                onClick={() => (sidebarCollapsed ? handleExpandSidebar() : setSidebarOpen(!sidebarOpen))}
                className={cn(
                  'glass-interactive p-2 rounded-lg hover:bg-black/[0.05] dark:hover:bg-white/[0.08] text-slate-600 dark:text-slate-400',
                  !sidebarCollapsed && 'md:hidden'
                )}
                title={sidebarCollapsed ? 'Show conversations (⌘K)' : sidebarOpen ? 'Close conversations' : 'Open conversations'}
                aria-label={sidebarCollapsed ? 'Show conversations (⌘K)' : sidebarOpen ? 'Close conversations' : 'Open conversations'}
              >
                {sidebarCollapsed ? <ChevronRight className="w-5 h-5" /> : sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
              </button>
              <div className="min-w-0">
                <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100 truncate">Chat</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 truncate">
                  {readyDocuments.length > 0
                    ? `${readyDocuments.length} doc${readyDocuments.length > 1 ? 's' : ''} ready`
                    : 'Upload documents to start'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
              {currentConversation && currentConversation.messages.length > 0 && (
                <div className="relative" ref={exportMenuRef}>
                  <button
                    type="button"
                    onClick={() => setShowExportMenu(!showExportMenu)}
                    className="glass-interactive flex items-center gap-1.5 px-2.5 py-2 rounded-lg glass hover:bg-black/[0.07] dark:hover:bg-white/[0.1] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 text-sm"
                    title="Export conversation"
                    aria-label="Export conversation"
                    aria-expanded={showExportMenu}
                    aria-haspopup="menu"
                  >
                    <Download className="w-4 h-4" />
                    <span className="hidden sm:inline">Export</span>
                  </button>
                  {showExportMenu && (
                    <div
                      role="menu"
                      className="absolute right-0 top-full mt-1 z-50 w-44 rounded-lg glass border border-white/20 dark:border-white/10 py-1 shadow-lg"
                    >
                      <button
                        role="menuitem"
                        onClick={() => { onExportChat('markdown'); setShowExportMenu(false); }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-black/[0.05] dark:hover:bg-white/[0.08] hover:text-slate-900 dark:hover:text-slate-100"
                      >
                        <FileText className="w-4 h-4" />
                        Markdown (.md)
                      </button>
                      <button
                        role="menuitem"
                        onClick={() => { onExportChat('json'); setShowExportMenu(false); }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-black/[0.05] dark:hover:bg-white/[0.08] hover:text-slate-900 dark:hover:text-slate-100"
                      >
                        <Braces className="w-4 h-4" />
                        JSON (.json)
                      </button>
                    </div>
                  )}
                </div>
              )}
              {readyDocuments.length > 0 && (
                <div className="flex items-center gap-2" title="Limit chat to specific document (or all in workspace)">
                  <select
                    value={selectedDocumentId}
                    onChange={(e) => setSelectedDocumentId(e.target.value)}
                    aria-label="Document scope for chat"
                    className="glass-interactive rounded-lg glass-input text-slate-900 dark:text-slate-100 text-sm px-3 py-2 pr-8 focus:outline-none focus:ring-1 focus:ring-slate-400/50 dark:focus:ring-slate-500/50 min-w-[140px]"
                  >
                    <option value="">All documents</option>
                    {readyDocuments.map((d) => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>
              )}
              {workspaces.length > 0 && (
                <div className="flex items-center gap-2" title="Chat uses documents from the selected workspace">
                  <select
                    value={selectedWorkspaceId ?? ''}
                    onChange={(e) => setSelectedWorkspaceId(e.target.value || null)}
                    aria-label="Workspace for chat context"
                    className="glass-interactive rounded-lg glass-input text-slate-900 dark:text-slate-100 text-sm px-3 py-2 pr-8 focus:outline-none focus:ring-1 focus:ring-slate-400/50 dark:focus:ring-slate-500/50 min-w-[140px]"
                  >
                    <option value="">All documents</option>
                    {workspaces.map((w) => (
                      <option key={w.id} value={w.id}>{w.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
});

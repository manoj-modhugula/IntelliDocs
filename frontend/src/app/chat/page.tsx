'use client';

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, X, ChevronDown } from 'lucide-react';
import { format } from 'date-fns';
import { useChatStore, Citation } from '@/store/chatStore';
import { useDocumentStore } from '@/store/documentStore';
import { useAuthStore } from '@/store/authStore';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { cn } from '@/lib/utils';
import { fetchWorkspaces, fetchSkills, createSkill, syncConversationMessages, type SkillItem } from '@/lib/api';
import { ApiError } from '@/lib/api';
import { handleUnauthorized } from '@/lib/authFailure';
import { toast } from '@/components/ui/Toaster';

import { ChatMessage, DEFAULT_FOLLOW_UP_SUGGESTIONS } from '@/components/chat/ChatMessage';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatEmptyState } from '@/components/chat/ChatEmptyState';
import { ChatStatusIndicator } from '@/components/chat/ChatStatusIndicator';
import { useSSEStream, type ChatStatus } from '@/hooks/useSSEStream';
import { useChatKeyboard } from '@/hooks/useChatKeyboard';
import { ChatMessageSkeleton } from '@/components/ui/Skeleton';
import { DragDropOverlay } from '@/components/ui/DragDropOverlay';
import { exportConversationToMarkdown } from '@/lib/exportConversation';
import { SourceViewer, type SourceViewerTarget } from '@/components/documents/SourceViewer';

const BUILT_IN_SKILLS = [{ id: 'short', name: 'Short' }] as const;
const BUILT_IN_SKILL_IDS = new Set<string>(BUILT_IN_SKILLS.map((s) => s.id));



function exportConversationToJSON(
  messages: { role: string; content: string; citations?: { documentName: string; pageNumber?: number }[] }[],
  title: string
): string {
  const exportData = {
    title,
    exportedAt: new Date().toISOString(),
    messageCount: messages.length,
    messages: messages.map((msg, idx) => ({
      index: idx + 1,
      role: msg.role,
      content: msg.content.trim(),
      citations: msg.citations?.map((c, i) => ({
        id: i + 1,
        document: c.documentName,
        page: c.pageNumber ?? null,
      })) ?? [],
    })),
  };
  return JSON.stringify(exportData, null, 2);
}

export default function ChatPage() {
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [streamingStatus, setStreamingStatus] = useState<ChatStatus>('complete');
  const [streamingMessage, setStreamingMessage] = useState<string>('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [fullFocusMode, setFullFocusMode] = useState(false);
  const [leftPanelView, setLeftPanelView] = useState<'chats' | 'documents'>('chats');
  const [showScrollFab, setShowScrollFab] = useState(false);
  const documentUploadInputRef = useRef<HTMLInputElement>(null!);
  const [showCreateSkillModal, setShowCreateSkillModal] = useState(false);
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillAction, setNewSkillAction] = useState('');
  const [creatingSkill, setCreatingSkill] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [sourceTarget, setSourceTarget] = useState<SourceViewerTarget | null>(null);
  const [showShortcuts, setShowShortcuts] = useState(false);

  // Sync persisted UI prefs from localStorage after mount (avoids hydration mismatch)
  useEffect(() => {
    try {
      setSidebarCollapsed(window.localStorage.getItem('intellidocs-chat-sidebar-collapsed') === 'true');
      setFullFocusMode(window.localStorage.getItem('intellidocs-chat-full-focus') === 'true');
    } catch {
      // ignore
    }
  }, []);

  const [selectedDocumentId, setSelectedDocumentId] = useState<string>('');
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [userSkills, setUserSkills] = useState<SkillItem[]>([]);
  const { cachedWorkspaces, setCachedWorkspaces, validateSelectedWorkspace, setOwnerUserId } = useWorkspaceStore();

  const chatSkills = useMemo(
    () => [
      ...BUILT_IN_SKILLS,
      ...userSkills
        .filter((s) => !BUILT_IN_SKILL_IDS.has(s.name.toLowerCase()))
        .map((s) => ({ id: s.name, name: s.name.charAt(0).toUpperCase() + s.name.slice(1).replace(/_/g, ' ') })),
    ],
    [userSkills]
  );
  const [workspaces, setWorkspaces] = useState<{ id: string; name: string }[]>(() => cachedWorkspaces);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const pendingContentRef = useRef('');
  const lastContentRef = useRef('');
  const lastFlushRef = useRef(0);
  const flushTimerRef = useRef<number | null>(null);

  const {
    conversations,
    getCurrentConversationId,
    createConversation,
    createConversationOnBackend,
    addMessage,
    updateMessage,
    setMessageStreaming,
    addCitations,
    setFollowUpSuggestions,
    setLoading,
    setCurrentConversation,
    deleteConversation,
    togglePinMessage,
    togglePinConversation,
  } = useChatStore();

  const { documents, loadFromBackend, uploadDocument, isUploading } = useDocumentStore();
  const token = useAuthStore((s) => s.token);
  const currentUserId = useAuthStore((s) => s.user?.id ?? null);
  const userDefaultWorkspaceId = useAuthStore((s) => s.user?.workspace_id ?? null);
  const { selectedWorkspaceId, setSelectedWorkspaceId, setDefaultFromUser } = useWorkspaceStore();
  const effectiveWorkspaceId =
    selectedWorkspaceId && selectedWorkspaceId !== ''
      ? selectedWorkspaceId
      : userDefaultWorkspaceId ?? undefined;

  const readyDocuments = useMemo(
    () =>
      documents.filter(
        (d) =>
          d.status === 'ready' &&
          (!effectiveWorkspaceId || String(d.workspaceId ?? '') === String(effectiveWorkspaceId))
      ),
    [documents, effectiveWorkspaceId]
  );

  const workspaceKey = selectedWorkspaceId ?? '';
  const conversationsInWorkspace = useMemo(
    () => conversations.filter((c) => (c.workspaceId ?? '') === workspaceKey),
    [conversations, workspaceKey]
  );
  const currentConversationId = getCurrentConversationId(workspaceKey);
  const isLoading = useChatStore((s) => s.isLoading);

  // Load workspaces
  useEffect(() => {
    if (!token) return;
    setDefaultFromUser(useAuthStore.getState().user?.workspace_id);
  }, [token, setDefaultFromUser]);

  // Load workspaces, skills, documents, and conversations in ONE batched request
  // This eliminates the 4+ simultaneous requests that were firing on mount
  const { syncFromBackend } = useChatStore();
  useEffect(() => {
    if (!token) {
      setInitialLoading(false);
      return;
    }
    // Seed from cache immediately for instant UI
    if (cachedWorkspaces.length > 0) {
      setWorkspaces(cachedWorkspaces);
    }

    const loadAll = async () => {
      try {
        const [workspaceList, skillList] = await Promise.allSettled([
          fetchWorkspaces(token),
          fetchSkills(token),
        ]);

        if (workspaceList.status === 'fulfilled') {
          const list = workspaceList.value;
          setWorkspaces(list);
          setCachedWorkspaces(list);
          validateSelectedWorkspace(list);
          setOwnerUserId(currentUserId);
        }

        if (skillList.status === 'fulfilled') {
          setUserSkills(skillList.value);
        }

        await Promise.allSettled([
          loadFromBackend(effectiveWorkspaceId),
          syncFromBackend(token, effectiveWorkspaceId),
        ]);
      } finally {
        setInitialLoading(false);
      }
    };

    if (!token) {
      setInitialLoading(false);
      return;
    }

    loadAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Derived conversation data
  const currentConversation = conversationsInWorkspace.find((c) => c.id === currentConversationId);
  const messages = useMemo(() => currentConversation?.messages ?? [], [currentConversation]);
  const pinnedIds = useMemo(() => new Set(currentConversation?.pinnedMessageIds ?? []), [currentConversation?.pinnedMessageIds]);
  const pinnedMessages = useMemo(() => messages.filter((m) => m.role === 'assistant' && pinnedIds.has(m.id)), [messages, pinnedIds]);
  const unpinnedMessages = useMemo(() => messages.filter((m) => !pinnedIds.has(m.id)), [messages, pinnedIds]);

  const conversationsSorted = useMemo(
    () =>
      [...conversationsInWorkspace].sort((a, b) => {
        const pinA = a.isPinned ?? false;
        const pinB = b.isPinned ?? false;
        if (pinA !== pinB) return pinA ? -1 : 1;
        const ta = typeof a.updatedAt === 'string' ? new Date(a.updatedAt).getTime() : a.updatedAt.getTime();
        const tb = typeof b.updatedAt === 'string' ? new Date(b.updatedAt).getTime() : b.updatedAt.getTime();
        return tb - ta;
      }),
    [conversationsInWorkspace]
  );

  // --- Callbacks ---------------------------------------------------------------─

  const { deleteConversationOnBackend, renameConversation } = useChatStore();

  useEffect(() => {
    const onShow = () => setShowShortcuts(true);
    window.addEventListener('intellidocs:show-shortcuts', onShow);
    return () => window.removeEventListener('intellidocs:show-shortcuts', onShow);
  }, []);

  const handleNewChat = useCallback(async () => {
    const newId = await createConversationOnBackend(effectiveWorkspaceId);
    setCurrentConversation(newId, workspaceKey);
    setSidebarOpen(false);
  }, [createConversationOnBackend, setCurrentConversation, workspaceKey, effectiveWorkspaceId]);

  const handleSelectConversation = useCallback(
    (id: string) => {
      setCurrentConversation(id, workspaceKey);
      setSidebarOpen(false);
    },
    [setCurrentConversation, workspaceKey]
  );

  // This is called by ChatSidebar ONLY after the exit animation completes.
  // The sidebar manages the visual animation state; this function removes the item from the store.
  // Called by sidebar after exit animation completes - removes from store
  const handleAnimationDeleteComplete = useCallback(
    (id: string) => {
      const wasCurrent = id === currentConversationId;
      deleteConversationOnBackend(id);
      if (wasCurrent && conversationsInWorkspace.length > 1) {
        const remaining = conversationsInWorkspace.filter((c) => c.id !== id);
        const next = remaining[0];
        if (next) setCurrentConversation(next.id, workspaceKey);
      } else if (wasCurrent) {
        setCurrentConversation(null, workspaceKey);
      }
      setSidebarOpen(false);
    },
    [currentConversationId, conversationsInWorkspace, deleteConversationOnBackend, setCurrentConversation, workspaceKey]
  );

  const handleExportChat = useCallback((format: 'markdown' | 'json' = 'markdown') => {
    if (!currentConversation || currentConversation.messages.length === 0) return;
    const title = (currentConversation.title || 'Chat').replace(/[^\w\s-]/g, '').slice(0, 50).trim() || 'chat';
    const baseName = `intellidocs-${title}-${currentConversation.id.slice(0, 8)}`;

    if (format === 'json') {
      const json = exportConversationToJSON(
        currentConversation.messages,
        currentConversation.title || 'Chat export'
      );
      const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${baseName}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } else {
      const md = exportConversationToMarkdown(
        currentConversation.messages,
        currentConversation.title || 'Chat export'
      );
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${baseName}.md`;
      a.click();
      URL.revokeObjectURL(url);
    }
    toast('success', `Exported as ${format.toUpperCase()}`);
  }, [currentConversation]);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'auto') => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior, block: 'end' });
    });
  }, []);

  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      scrollToBottom('auto');
    }
  }, [messages, scrollToBottom]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Cleanup flush timer on unmount
  useEffect(() => {
    return () => {
      if (flushTimerRef.current) {
        window.clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
    };
  }, []);

  // Keyboard shortcuts
  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem('intellidocs-chat-sidebar-collapsed', String(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  const handleToggleFullFocus = useCallback(() => {
    setFullFocusMode((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem('intellidocs-chat-full-focus', String(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  const handleSwitchPanel = useCallback(() => {
    setLeftPanelView((v) => (v === 'chats' ? 'documents' : 'chats'));
  }, []);

  useChatKeyboard({
    onNewChat: handleNewChat,
    onToggleSidebar: handleToggleSidebar,
    onToggleFullFocus: handleToggleFullFocus,
    onSwitchPanel: handleSwitchPanel,
    inputRef,
  });

  const handleExpandSidebar = useCallback(() => {
    setSidebarCollapsed(false);
    try {
      window.localStorage.setItem('intellidocs-chat-sidebar-collapsed', 'false');
    } catch {
      // ignore
    }
  }, []);

  const handleAddDocumentClick = useCallback(() => {
    documentUploadInputRef.current?.click();
  }, []);

  const handleFileUpload = useCallback(
    async (file: File) => {
      const wsId = effectiveWorkspaceId ?? undefined;
      try {
        await uploadDocument(file, wsId);
        toast('success', `${file.name} uploaded; it will appear in this workspace when ready.`);
        loadFromBackend(effectiveWorkspaceId ?? undefined);
        const t = useAuthStore.getState().token;
        if (t) fetchWorkspaces(t).then((list) => setCachedWorkspaces(list)).catch(() => {});
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Upload failed';
        toast('error', msg.includes('Upload failed') ? `Failed to upload ${file.name}` : msg);
      }
    },
    [effectiveWorkspaceId, uploadDocument, loadFromBackend, setCachedWorkspaces]
  );

  const handleDocumentFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      e.target.value = '';
      if (!file) return;
      await handleFileUpload(file);
    },
    [handleFileUpload]
  );

  const handleMessagesScroll = useCallback(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    shouldAutoScrollRef.current = distanceFromBottom < 80;
    setShowScrollFab(distanceFromBottom > 200 && messages.length > 0);
  }, [messages.length]);

  const scheduleStreamFlush = useCallback(
    (convId: string, messageId: string, force = false) => {
      const now = performance.now();
      const elapsed = now - lastFlushRef.current;
      const flush = () => {
        const nextContent = pendingContentRef.current;
        if (nextContent !== lastContentRef.current) {
          updateMessage(convId, messageId, nextContent);
          lastContentRef.current = nextContent;
        }
        lastFlushRef.current = performance.now();
      };
      if (force || elapsed >= 16) {
        if (flushTimerRef.current) {
          window.clearTimeout(flushTimerRef.current);
          flushTimerRef.current = null;
        }
        flush();
        return;
      }
      if (!flushTimerRef.current) {
        flushTimerRef.current = window.setTimeout(() => {
          flushTimerRef.current = null;
          flush();
        }, 16 - elapsed);
      }
    },
    [updateMessage]
  );

  // --- Chat streaming ---------------------------------------------------------

  const { streamChat, abortStreaming } = useSSEStream({ token });

  const sendMessage = useCallback(
    async (userMessage: string, contextChunkId?: string) => {
      if (!userMessage.trim() || isLoading) return;

      setError(null);
      setInput('');

      const skillToSend = selectedSkill;
      setSelectedSkill(null);

      if (inputRef.current) {
        inputRef.current.style.height = '56px';
      }

      let convId = currentConversationId;
      if (!convId) {
        convId = token
          ? await createConversationOnBackend(effectiveWorkspaceId)
          : createConversation(workspaceKey);
        setCurrentConversation(convId, workspaceKey);
      }

      addMessage(convId, { role: 'user', content: userMessage.trim() });

      const assistantMessageId = addMessage(convId, {
        role: 'assistant',
        content: '',
        isStreaming: true,
      });

      setLoading(true);
      setStreamingStatus('searching');
      setStreamingMessage('Searching documents...');
      pendingContentRef.current = '';
      lastContentRef.current = '';
      lastFlushRef.current = 0;
      if (flushTimerRef.current) {
        window.clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }

      try {
        await streamChat(
          userMessage.trim(),
          convId,
          assistantMessageId,
          selectedWorkspaceId ?? null,
          selectedDocumentId ? [selectedDocumentId] : undefined,
          contextChunkId,
          skillToSend,
          {
            onContent: (content) => { pendingContentRef.current += content; },
            onCitations: (citations) => addCitations(convId, assistantMessageId, citations),
            onFollowUps: (suggestions) =>
              setFollowUpSuggestions(convId, assistantMessageId, suggestions),
            onError: (msg) => setError(msg),
            onStatus: (status, msg) => {
              setStreamingStatus(status);
              if (msg) setStreamingMessage(msg);
            },
            onDone: () => {
              setMessageStreaming(convId, assistantMessageId, false);
              setStreamingStatus('complete');
              const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
              if (token && conv) {
                const lastUser = [...conv.messages].reverse().find((m) => m.role === 'user');
                const assistant = conv.messages.find((m) => m.id === assistantMessageId);
                const turn = [lastUser, assistant].filter(Boolean) as typeof conv.messages;
                void syncConversationMessages(
                  token,
                  convId,
                  turn.map((m) => ({
                    id: m.id,
                    role: m.role,
                    content: m.content,
                    citations: m.citations,
                    followUpSuggestions: m.followUpSuggestions,
                    createdAt:
                      m.createdAt instanceof Date ? m.createdAt.toISOString() : String(m.createdAt),
                  }))
                );
              }
              renameConversation(convId);
            },
            scheduleFlush: scheduleStreamFlush,
          }
        );
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          setMessageStreaming(convId, assistantMessageId, false);
          setStreamingStatus('complete');
          return;
        }
        const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
        if (/\b401\b/.test(errorMessage) || /unauthorized/i.test(errorMessage)) {
          handleUnauthorized(401);
        }
        setError(errorMessage);
        updateMessage(convId, assistantMessageId, 'Sorry, I encountered an error. Please try again.');
        setMessageStreaming(convId, assistantMessageId, false);
        setStreamingStatus('error');
      } finally {
        if (flushTimerRef.current) {
          window.clearTimeout(flushTimerRef.current);
          flushTimerRef.current = null;
        }
        setLoading(false);
      }
    },
    [
      isLoading,
      currentConversationId,
      createConversation,
      createConversationOnBackend,
      token,
      effectiveWorkspaceId,
      setCurrentConversation,
      workspaceKey,
      addMessage,
      updateMessage,
      setMessageStreaming,
      addCitations,
      setFollowUpSuggestions,
      setLoading,
      scheduleStreamFlush,
      selectedDocumentId,
      selectedSkill,
      selectedWorkspaceId,
      streamChat,
      renameConversation,
    ]
  );

  const handleSubmit = useCallback(
    (value: string) => {
      sendMessage(value);
    },
    [sendMessage]
  );

  const handleCreateSkill = useCallback(
    async (name: string, action: string) => {
      if (!token) return;
      setCreatingSkill(true);
      try {
        await createSkill(token, { name, action });
        const list = await fetchSkills(token);
        setUserSkills(list);
        toast('success', `Skill /${name} created`);
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : 'Failed to create skill';
        toast('error', msg);
      } finally {
        setCreatingSkill(false);
      }
    },
    [token]
  );

  const handleTogglePinConversation = useCallback(
    (id: string) => {
      togglePinConversation(id);
    },
    [togglePinConversation]
  );

  // --- Render ---------------------------------------------------------------──

  return (
    <div className="h-full flex min-h-0">
      {/* Sidebar */}
      <ChatSidebar
        sidebarOpen={sidebarOpen}
        sidebarCollapsed={sidebarCollapsed}
        setSidebarOpen={setSidebarOpen}
        setSidebarCollapsed={setSidebarCollapsed}
        handleExpandSidebar={handleExpandSidebar}
        leftPanelView={leftPanelView}
        setLeftPanelView={setLeftPanelView}
        selectedDocumentId={selectedDocumentId}
        setSelectedDocumentId={setSelectedDocumentId}
        documentUploadInputRef={documentUploadInputRef}
        handleAddDocumentClick={handleAddDocumentClick}
        handleDocumentFileChange={handleDocumentFileChange}
        isUploading={isUploading}
        currentConversationId={currentConversationId}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
        onAnimationDeleteComplete={handleAnimationDeleteComplete}
        onTogglePinConversation={handleTogglePinConversation}
        conversationsSorted={conversationsSorted}
        currentWorkspaceKey={workspaceKey}
      />

      {/* Main chat area */}
      <div className="relative flex-1 flex flex-col min-w-0 min-h-0">
        <ChatHeader
          sidebarOpen={sidebarOpen}
          sidebarCollapsed={sidebarCollapsed}
          setSidebarOpen={setSidebarOpen}
          setSidebarCollapsed={setSidebarCollapsed}
          handleExpandSidebar={handleExpandSidebar}
          fullFocusMode={fullFocusMode}
          setFullFocusMode={setFullFocusMode}
          readyDocuments={readyDocuments}
          selectedDocumentId={selectedDocumentId}
          setSelectedDocumentId={setSelectedDocumentId}
          workspaces={workspaces}
          selectedWorkspaceId={selectedWorkspaceId}
          setSelectedWorkspaceId={setSelectedWorkspaceId}
          currentConversation={currentConversation ?? null}
          onExportChat={handleExportChat}
        />

        {/* Error Banner */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex-shrink-0 bg-rose-50 dark:bg-rose-950/30 border-b border-rose-200 dark:border-rose-800 px-4 sm:px-6 py-3"
            >
              <div className="max-w-4xl mx-auto flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" aria-hidden />
                <p className="text-sm text-rose-800 dark:text-rose-200 flex-1">{error}</p>
                <button
                  type="button"
                  onClick={() => setError(null)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-rose-800 dark:text-rose-200 bg-rose-100 dark:bg-rose-900/40 hover:bg-rose-200 dark:hover:bg-rose-900/60 transition-colors"
                  aria-label="Dismiss error"
                >
                  <X className="w-4 h-4" />
                  Dismiss
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Messages area */}
        <div className="flex-1 flex min-h-0 min-w-0">
          <div
            ref={messagesContainerRef}
            onScroll={handleMessagesScroll}
            role="log"
            aria-label="Chat messages"
            aria-live="polite"
            className="flex-1 overflow-y-auto overflow-anchor-auto min-h-0 scroll-region min-w-0"
          >
            {initialLoading ? (
              <ChatMessageSkeleton count={4} />
            ) : messages.length === 0 ? (
              <ChatEmptyState
                readyDocumentsCount={readyDocuments.length}
                documentNames={readyDocuments.map((d) => d.name)}
                onSuggestionClick={(q) => {
                  setInput(q);
                  inputRef.current?.focus();
                }}
                onFocusInput={() => inputRef.current?.focus()}
              />
            ) : (
              <div className="max-w-4xl mx-auto py-4 sm:py-6 px-3 sm:px-4">
                {pinnedMessages.length > 0 && (
                  <div className="mb-4 pb-4 border-b border-white/10 dark:border-white/5">
                    <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 px-1">Pinned</p>
                    <div className="space-y-3">
                      {pinnedMessages.map((message) => (
                        <ChatMessage
                          key={message.id}
                          message={message}
                          isPinned
                          onPin={currentConversationId ? () => togglePinMessage(currentConversationId, message.id) : undefined}
                          followUpSuggestions={
                            message.followUpSuggestions?.length
                              ? message.followUpSuggestions
                              : DEFAULT_FOLLOW_UP_SUGGESTIONS
                          }
                          onFollowUpClick={sendMessage}
                          onAskAboutChunk={(citation) => {
                            sendMessage('Explain this passage in more detail.', citation.chunkId);
                          }}
                          onOpenSource={(citation) => {
                            setSourceTarget({
                              documentId: citation.documentId,
                              documentName: citation.documentName,
                              pageNumber: citation.pageNumber,
                              chunkText: citation.chunkText,
                              bbox: citation.bbox,
                              chunkType: citation.chunkType,
                            });
                          }}
                        />
                      ))}
                    </div>
                  </div>
                )}
                {unpinnedMessages.map((message) => (
                  <ChatMessage
                    key={message.id}
                    message={message}
                    isPinned={pinnedIds.has(message.id)}
                    onPin={currentConversationId ? () => togglePinMessage(currentConversationId, message.id) : undefined}
                    followUpSuggestions={
                      message.followUpSuggestions?.length
                        ? message.followUpSuggestions
                        : DEFAULT_FOLLOW_UP_SUGGESTIONS
                    }
                    onFollowUpClick={sendMessage}
                    onAskAboutChunk={(citation) => {
                      sendMessage('Explain this passage in more detail.', citation.chunkId);
                    }}
                    onOpenSource={(citation) => {
                      setSourceTarget({
                        documentId: citation.documentId,
                        documentName: citation.documentName,
                        pageNumber: citation.pageNumber,
                        chunkText: citation.chunkText,
                        bbox: citation.bbox,
                        chunkType: citation.chunkType,
                      });
                    }}
                  />
                ))}
                <div ref={messagesEndRef} className="h-4 flex-shrink-0" aria-hidden />
                <ChatStatusIndicator status={streamingStatus} message={streamingMessage} className="px-4 py-2" />

                {/* Scroll-to-bottom FAB - CSS-only spring entrance, AnimatePresence for mount/unmount */}
                <AnimatePresence>
                  {showScrollFab && (
                    <button
                      onClick={() => scrollToBottom('smooth')}
                      className="scroll-to-bottom-fab scroll-to-bottom-fab-animated"
                      aria-label="Scroll to bottom"
                      title="Scroll to bottom"
                    >
                      <ChevronDown className="w-5 h-5" />
                    </button>
                  )}
                </AnimatePresence>
              </div>
            )}
          </div>
        </div>

        {/* Input */}
        <ChatInput
          input={input}
          setInput={setInput}
          onSubmit={handleSubmit}
          onStop={abortStreaming}
          isLoading={isLoading}
          disabled={readyDocuments.length === 0}
          placeholder={
            readyDocuments.length > 0
              ? 'Ask…'
              : 'Upload documents first'
          }
          chatSkills={chatSkills}
          selectedSkill={selectedSkill}
          setSelectedSkill={setSelectedSkill}
          onCreateSkill={handleCreateSkill}
          creatingSkill={creatingSkill}
          readyDocumentsCount={readyDocuments.length}
        />

        {/* Global drag & drop overlay for document upload */}
        <DragDropOverlay
          onFileDrop={handleFileUpload}
          disabled={isUploading}
        />
      </div>
      {sourceTarget && (
        <SourceViewer
          target={sourceTarget}
          token={token}
          onClose={() => setSourceTarget(null)}
        />
      )}
      {showShortcuts && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-slate-900/40 dark:bg-black/60"
          role="dialog"
          aria-modal="true"
          aria-labelledby="shortcuts-title"
          onClick={() => setShowShortcuts(false)}
        >
          <div
            className="w-full max-w-md rounded-xl glass-modal border border-white/20 dark:border-white/10 p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="shortcuts-title" className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Keyboard shortcuts
            </h2>
            <ul className="mt-4 space-y-2 text-sm text-slate-700 dark:text-slate-300">
              <li><kbd className="font-mono text-xs">⌘/Ctrl + N</kbd> New chat</li>
              <li><kbd className="font-mono text-xs">⌘/Ctrl + K</kbd> Toggle sidebar</li>
              <li><kbd className="font-mono text-xs">⌘/Ctrl + Shift + K</kbd> Full focus</li>
              <li><kbd className="font-mono text-xs">⌘/Ctrl + M</kbd> Chats / documents panel</li>
              <li><kbd className="font-mono text-xs">⌘/Ctrl + /</kbd> This help</li>
              <li><kbd className="font-mono text-xs">Esc</kbd> Close</li>
            </ul>
            <button
              type="button"
              className="mt-4 rounded-lg px-3 py-1.5 text-sm glass"
              onClick={() => setShowShortcuts(false)}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

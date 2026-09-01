import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { generateId } from '@/lib/utils';
import { useAuthStore } from '@/store/authStore';

export interface CitationBBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface Citation {
  id: string;
  chunkId?: string;
  documentId: string;
  documentName: string;
  pageNumber?: number;
  chunkText: string;
  relevanceScore: number;
  chunkType?: string;
  bbox?: CitationBBox | null;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  followUpSuggestions?: string[];
  createdAt: Date;
  isStreaming?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  pinnedMessageIds?: string[];
  isPinned?: boolean;
  createdAt: Date;
  updatedAt: Date;
  workspaceId?: string;
}

interface ChatState {
  conversations: Conversation[];
  currentConversationIdByWorkspace: Record<string, string | null>;
  isLoading: boolean;
  ownerUserId: string | null;
  hasSyncedFromBackend: boolean;

  createConversation: (workspaceId: string) => string;
  createConversationOnBackend: (workspaceId?: string | null) => Promise<string>;
  deleteConversation: (id: string) => void;
  deleteConversationOnBackend: (id: string) => Promise<void>;
  setCurrentConversation: (id: string | null, workspaceId: string) => void;
  getCurrentConversationId: (workspaceId: string) => string | null;
  addMessage: (conversationId: string, message: Omit<Message, 'id' | 'createdAt'>) => string;
  updateMessage: (conversationId: string, messageId: string, content: string) => void;
  setMessageStreaming: (conversationId: string, messageId: string, isStreaming: boolean) => void;
  addCitations: (conversationId: string, messageId: string, citations: Citation[]) => void;
  setFollowUpSuggestions: (conversationId: string, messageId: string, suggestions: string[]) => void;
  setLoading: (loading: boolean) => void;
  clearOldConversations: () => void;
  clearWorkspaceConversations: (workspaceId: string) => void;
  setOwnerUserId: (userId: string | null) => void;
  togglePinMessage: (conversationId: string, messageId: string) => void;
  togglePinConversation: (conversationId: string) => void;
  clearOnLogout: () => void;
  syncFromBackend: (token: string, workspaceId?: string | null) => Promise<void>;
  updateConversationTitle: (conversationId: string, title: string) => void;
  renameConversation: (conversationId: string) => Promise<void>;
}

const MAX_CONVERSATIONS = 20;
const MAX_MESSAGES_PER_CONV = 50;

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      conversations: [],
      currentConversationIdByWorkspace: {},
      isLoading: false,
      ownerUserId: null,
      hasSyncedFromBackend: false,

      createConversation: (workspaceId) => {
        const currentUserId = useAuthStore.getState().user?.id ?? null;
        const ownerUserId = get().ownerUserId ?? null;
        if (ownerUserId && ownerUserId !== currentUserId) {
          set({
            conversations: [],
            currentConversationIdByWorkspace: {},
            ownerUserId: currentUserId,
          });
        } else if (!ownerUserId && currentUserId) {
          set({ ownerUserId: currentUserId });
        }
        const id = generateId();
        const newConversation: Conversation = {
          id,
          title: 'New Chat',
          messages: [],
          pinnedMessageIds: [],
          createdAt: new Date(),
          updatedAt: new Date(),
          workspaceId: workspaceId ?? '',
        };
        set((state) => {
          const conversations = [newConversation, ...state.conversations].slice(0, MAX_CONVERSATIONS);
          const currentConversationIdByWorkspace = { ...state.currentConversationIdByWorkspace, [workspaceId]: id };
          return { conversations, currentConversationIdByWorkspace };
        });
        return id;
      },

      createConversationOnBackend: async (workspaceId) => {
        const token = useAuthStore.getState().token;
        if (!token) return get().createConversation(workspaceId ?? '');
        try {
          const { createConversation: createConv } = await import('@/lib/api');
          const conv = await createConv(token, workspaceId);
          const newConversation: Conversation = {
            id: conv.id,
            title: conv.title,
            messages: conv.messages.map((m) => ({
              ...m,
              createdAt: new Date(m.createdAt),
            })),
            pinnedMessageIds: conv.pinnedMessageIds,
            isPinned: conv.isPinned,
            createdAt: new Date(conv.createdAt),
            updatedAt: new Date(conv.updatedAt),
            workspaceId: conv.workspaceId ?? '',
          };
          set((state) => {
            const exists = state.conversations.some((c) => c.id === conv.id);
            if (exists) return state;
            const conversations = [newConversation, ...state.conversations].slice(0, MAX_CONVERSATIONS);
            const currentConversationIdByWorkspace = {
              ...state.currentConversationIdByWorkspace,
              [workspaceId ?? '']: conv.id,
            };
            return { conversations, currentConversationIdByWorkspace };
          });
          return conv.id;
        } catch {
          return get().createConversation(workspaceId ?? '');
        }
      },

      deleteConversation: (id) => {
        set((state) => {
          const conv = state.conversations.find((c) => c.id === id);
          const workspaceId = conv?.workspaceId ?? '';
          const conversations = state.conversations.filter((c) => c.id !== id);
          const currentConversationIdByWorkspace = { ...state.currentConversationIdByWorkspace };
          if (currentConversationIdByWorkspace[workspaceId] === id) {
            currentConversationIdByWorkspace[workspaceId] = null;
          }
          return { conversations, currentConversationIdByWorkspace };
        });
      },

      deleteConversationOnBackend: async (id) => {
        // Remove locally first so UI transitions complete cleanly with no flicker.
        get().deleteConversation(id);
        const token = useAuthStore.getState().token;
        if (!token) return;
        try {
          const { deleteConversation: deleteConv } = await import('@/lib/api');
          await deleteConv(token, id);
        } catch {
          // Non-fatal: local delete still applies
        }
      },

      setCurrentConversation: (id, workspaceId) => {
        set((state) => ({
          currentConversationIdByWorkspace: { ...state.currentConversationIdByWorkspace, [workspaceId]: id },
        }));
      },

      getCurrentConversationId: (workspaceId) => {
        return get().currentConversationIdByWorkspace[workspaceId ?? ''] ?? null;
      },

      addMessage: (conversationId, message) => {
        const messageId = generateId();
        const newMessage: Message = {
          ...message,
          id: messageId,
          createdAt: new Date(),
        };
        
        set((state) => ({
          conversations: state.conversations.map((conv) => {
            if (conv.id !== conversationId) return conv;
            
            // Limit messages per conversation
            const messages = [...conv.messages, newMessage].slice(-MAX_MESSAGES_PER_CONV);
            
            return {
              ...conv,
              messages,
              updatedAt: new Date(),
              title: conv.messages.length === 0 && message.role === 'user'
                ? message.content.slice(0, 40) + (message.content.length > 40 ? '...' : '')
                : conv.title,
            };
          }),
        }));
        return messageId;
      },

      updateMessage: (conversationId, messageId, content) => {
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: conv.messages.map((msg) =>
                    msg.id === messageId ? { ...msg, content } : msg
                  ),
                }
              : conv
          ),
        }));
      },

      setMessageStreaming: (conversationId, messageId, isStreaming) => {
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: conv.messages.map((msg) =>
                    msg.id === messageId ? { ...msg, isStreaming } : msg
                  ),
                }
              : conv
          ),
        }));
      },

      addCitations: (conversationId, messageId, citations) => {
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: conv.messages.map((msg) =>
                    msg.id === messageId ? { ...msg, citations } : msg
                  ),
                }
              : conv
          ),
        }));
      },

      setFollowUpSuggestions: (conversationId, messageId, suggestions) => {
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: conv.messages.map((msg) =>
                    msg.id === messageId ? { ...msg, followUpSuggestions: suggestions } : msg
                  ),
                }
              : conv
          ),
        }));
      },

      setLoading: (loading) => {
        set({ isLoading: loading });
      },

      clearOldConversations: () => {
        set((state) => ({
          conversations: state.conversations.slice(0, MAX_CONVERSATIONS),
        }));
      },

      clearWorkspaceConversations: (workspaceId) =>
        set((state) => {
          const conversations = state.conversations.filter(
            (conv) => (conv.workspaceId ?? '') !== workspaceId
          );
          const currentConversationIdByWorkspace = { ...state.currentConversationIdByWorkspace };
          if (currentConversationIdByWorkspace[workspaceId]) {
            currentConversationIdByWorkspace[workspaceId] = null;
          }
          return { conversations, currentConversationIdByWorkspace };
        }),

      setOwnerUserId: (userId) => set({ ownerUserId: userId }),

      togglePinMessage: (conversationId, messageId) => {
        set((state) => ({
          conversations: state.conversations.map((conv) => {
            if (conv.id !== conversationId) return conv;
            const pinned = conv.pinnedMessageIds ?? [];
            const isPinned = pinned.includes(messageId);
            const nextPinned = isPinned
              ? pinned.filter((id) => id !== messageId)
              : [...pinned, messageId];
            return { ...conv, pinnedMessageIds: nextPinned };
          }),
        }));
        const token = useAuthStore.getState().token;
        const conv = get().conversations.find((c) => c.id === conversationId);
        if (token && conv) {
          void import('@/lib/api').then(({ updateConversation }) =>
            updateConversation(token, conversationId, {
              pinnedMessageIds: conv.pinnedMessageIds ?? [],
            }).catch(() => undefined)
          );
        }
      },

      togglePinConversation: (conversationId) => {
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? { ...conv, isPinned: !(conv.isPinned ?? false) }
              : conv
          ),
        }));
        const token = useAuthStore.getState().token;
        const conv = get().conversations.find((c) => c.id === conversationId);
        if (token && conv) {
          void import('@/lib/api').then(({ updateConversation }) =>
            updateConversation(token, conversationId, {
              isPinned: conv.isPinned ?? false,
            }).catch(() => undefined)
          );
        }
      },

      syncFromBackend: async (token: string, workspaceId?: string | null) => {
        try {
          const { fetchConversations } = await import('@/lib/api');
          const remoteConvs = await fetchConversations(token, workspaceId);

          set((state) => {
            // Merge: prefer backend data, but keep local-only conversations that aren't on backend
            const remoteIds = new Set(remoteConvs.map((c) => c.id));
            const localOnly = state.conversations.filter(
              (c) => !remoteIds.has(c.id)
            );

            const merged = [
              ...remoteConvs.map((c) => ({
                id: c.id,
                title: c.title,
                messages: c.messages.map((m) => ({
                  ...m,
                  createdAt: new Date(m.createdAt),
                })),
                pinnedMessageIds: c.pinnedMessageIds,
                isPinned: c.isPinned,
                createdAt: new Date(c.createdAt),
                updatedAt: new Date(c.updatedAt),
                workspaceId: c.workspaceId ?? '',
              })),
              ...localOnly,
            ].slice(0, MAX_CONVERSATIONS);

            return { conversations: merged, hasSyncedFromBackend: true };
          });
        } catch {
          // Non-fatal: keep local data
          set({ hasSyncedFromBackend: true });
        }
      },

      updateConversationTitle: (conversationId, title) => {
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId ? { ...conv, title } : conv
          ),
        }));
      },

      renameConversation: async (conversationId) => {
        const conv = get().conversations.find((c) => c.id === conversationId);
        if (!conv || conv.messages.length < 2) return;
        if (conv.title !== 'New Chat' && !conv.title.startsWith('New Chat')) return;

        const token = useAuthStore.getState().token;
        if (!token) return;

        try {
          const { generateConversationTitle } = await import('@/lib/api');
          // Convert Message[] (Date) to ConversationMessage[] (string) for API
          const apiMessages = conv.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            citations: m.citations,
            followUpSuggestions: m.followUpSuggestions,
            createdAt: m.createdAt instanceof Date ? m.createdAt.toISOString() : m.createdAt,
          }));
          const newTitle = await generateConversationTitle(token, apiMessages);
          if (newTitle) {
            get().updateConversationTitle(conversationId, newTitle);
            const { updateConversation } = await import('@/lib/api');
            await updateConversation(token, conversationId, { title: newTitle }).catch(
              () => undefined
            );
          }
        } catch {
          // Keep the existing title if generation fails.
        }
      },

      clearOnLogout: () =>
        set({
          conversations: [],
          currentConversationIdByWorkspace: {},
          isLoading: false,
          ownerUserId: null,
        }),
    }),
    {
      name: 'intellidocs-chat',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        conversations: state.conversations.slice(0, MAX_CONVERSATIONS).map((c) => ({
          ...c,
          workspaceId: c.workspaceId ?? '',
          pinnedMessageIds: c.pinnedMessageIds ?? [],
          isPinned: c.isPinned ?? false,
        })),
        currentConversationIdByWorkspace: state.currentConversationIdByWorkspace,
        ownerUserId: state.ownerUserId,
        hasSyncedFromBackend: state.hasSyncedFromBackend,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          const currentUserId = useAuthStore.getState().user?.id ?? null;
          if (state.ownerUserId && state.ownerUserId !== currentUserId) {
            state.clearOnLogout();
            state.setOwnerUserId(currentUserId);
          } else if (!state.ownerUserId && currentUserId) {
            state.setOwnerUserId(currentUserId);
          }
        }
      },
    }
  )
);

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { useAuthStore } from '@/store/authStore';

export interface CachedWorkspace {
  id: string;
  name: string;
  description?: string | null;
  documentCount: number;
  createdAt?: string;
  updatedAt?: string;
}

/**
 * Workspace selection and cached list for stale-while-revalidate.
 */
interface WorkspaceState {
  selectedWorkspaceId: string | null;
  cachedWorkspaces: CachedWorkspace[];
  ownerUserId: string | null;
  setSelectedWorkspaceId: (id: string | null) => void;
  setDefaultFromUser: (workspaceId: string | null | undefined) => void;
  setCachedWorkspaces: (ws: CachedWorkspace[]) => void;
  validateSelectedWorkspace: (ws: CachedWorkspace[]) => void;
  setOwnerUserId: (userId: string | null) => void;
  /** Clear cached data on logout to prevent leaking to next user */
  clearOnLogout: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      selectedWorkspaceId: null,
      cachedWorkspaces: [],
      ownerUserId: null,
      setSelectedWorkspaceId: (id) => set({ selectedWorkspaceId: id }),
      /** Only set default when no workspace is selected - don't overwrite user's choice */
      setDefaultFromUser: (workspaceId) =>
        set((state) => ({
          selectedWorkspaceId: state.selectedWorkspaceId ?? workspaceId ?? null,
        })),
      setCachedWorkspaces: (ws) => set({ cachedWorkspaces: ws }),
      validateSelectedWorkspace: (ws) =>
        set((state) => {
          if (!state.selectedWorkspaceId) return state;
          const exists = ws.some((w) => w.id === state.selectedWorkspaceId);
          return exists ? state : { selectedWorkspaceId: null };
        }),
      setOwnerUserId: (userId) => set({ ownerUserId: userId }),
      clearOnLogout: () =>
        set({ selectedWorkspaceId: null, cachedWorkspaces: [], ownerUserId: null }),
    }),
    {
      name: 'intellidocs-workspace',
      // Persist only selection – workspace list is always loaded from backend
      partialize: (s) => ({
        selectedWorkspaceId: s.selectedWorkspaceId,
        ownerUserId: s.ownerUserId,
      }),
      merge: (persisted, current) => {
        const p = persisted as Partial<WorkspaceState> | undefined;
        return {
          ...current,
          selectedWorkspaceId: p?.selectedWorkspaceId ?? current.selectedWorkspaceId,
          ownerUserId: p?.ownerUserId ?? current.ownerUserId,
          cachedWorkspaces: [], // never from storage; always fetch from backend
        };
      },
      onRehydrateStorage: () => (state) => {
        if (state) {
          const currentUserId = useAuthStore.getState().user?.id ?? null;
          if (state.ownerUserId && state.ownerUserId !== currentUserId) {
            state.clearOnLogout();
            state.setOwnerUserId(currentUserId);
          } else if (!state.ownerUserId && currentUserId) {
            state.setOwnerUserId(currentUserId);
          }
          // NOTE: fetchWorkspaces is intentionally NOT called here.
          // The chat page's loadAll() handles fetching and calls setCachedWorkspaces.
          // Calling it here would cause a duplicate simultaneous request race condition.
        }
      },
    }
  )
);

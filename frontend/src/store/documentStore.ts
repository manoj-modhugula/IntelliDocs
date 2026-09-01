import { create } from 'zustand';
import { generateId } from '@/lib/utils';
import { fetchWorkspaces } from '@/lib/api';
import { useAuthStore } from '@/store/authStore';
import { useWorkspaceStore } from '@/store/workspaceStore';

export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'error';

export interface Document {
  id: string;
  name: string;
  type: string;
  size: number;
  status: DocumentStatus;
  uploadedAt: Date;
  chunkCount?: number;
  errorMessage?: string;
  workspaceId?: string;
}

interface DocumentState {
  documents: Document[];
  isUploading: boolean;
  isLoading: boolean;
  lastSyncError: string | null;

  uploadDocument: (file: File, workspaceId?: string | null) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  updateDocumentStatus: (id: string, status: DocumentStatus, chunkCount?: number) => void;
  loadFromBackend: (workspaceId?: string | null) => Promise<void>;
  clearOnLogout: () => void;
}

const DOCUMENTS_API = '/api/documents';
const DOCUMENTS_UPLOAD_API = '/api/documents/upload';
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

let loadAbortController: AbortController | null = null;

export const useDocumentStore = create<DocumentState>()((set, get) => ({
  documents: [],
  isUploading: false,
  isLoading: false,
  lastSyncError: null,

  loadFromBackend: async (workspaceId?: string | null) => {
    const token = useAuthStore.getState().token;
    if (!token) {
      set({ documents: [], isLoading: false, lastSyncError: null });
      return;
    }

    if (loadAbortController) loadAbortController.abort();
    const controller = new AbortController();
    loadAbortController = controller;

    set({ isLoading: true, lastSyncError: null });

    const params = new URLSearchParams();
    if (workspaceId) params.set('workspaceId', workspaceId);
    const url = params.toString() ? `${DOCUMENTS_API}?${params.toString()}` : DOCUMENTS_API;

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        cache: 'no-store',
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const backendDocs = await response.json();
      const documents: Document[] = backendDocs.map((doc: any) => ({
        id: doc.id,
        name: doc.name,
        type: doc.type,
        size: doc.size,
        status: (doc.status || 'ready') as DocumentStatus,
        uploadedAt: doc.created_at ? new Date(doc.created_at) : new Date(),
        chunkCount: doc.chunkCount,
        errorMessage: doc.errorMessage,
        workspaceId: doc.workspace_id,
      }));

      if (!controller.signal.aborted) {
        set({ documents, isLoading: false, lastSyncError: null });
      }
    } catch (err) {
      if (controller.signal.aborted) return;
      const msg = err instanceof Error ? err.message : 'Failed to load documents';
      set({ isLoading: false, lastSyncError: msg });
    }
  },

  uploadDocument: async (file: File, workspaceId?: string | null) => {
    const token = useAuthStore.getState().token;
    const user = useAuthStore.getState().user;
    if (!token) {
      throw new Error('Please sign in before uploading documents');
    }

    const cachedWorkspaces = useWorkspaceStore.getState().cachedWorkspaces;
    const requestedWorkspaceId =
      workspaceId && (cachedWorkspaces.length === 0 || cachedWorkspaces.some((ws) => ws.id === workspaceId))
        ? workspaceId
        : null;
    const effectiveWorkspaceId = requestedWorkspaceId ?? user?.workspace_id ?? undefined;
    const docId = generateId();
    const newDoc: Document = {
      id: docId,
      name: file.name,
      type: file.type || 'application/octet-stream',
      size: file.size,
      status: 'pending',
      uploadedAt: new Date(),
      workspaceId: effectiveWorkspaceId,
    };

    set((s) => ({ documents: [newDoc, ...s.documents], isUploading: true }));

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('documentId', docId);
      if (effectiveWorkspaceId) formData.append('workspaceId', effectiveWorkspaceId);

      const response = await fetch(DOCUMENTS_UPLOAD_API, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err?.error || err?.detail || 'Upload failed');
      }

      const result = await response.json();
      const actualId = result.id || docId;
      const actualWorkspaceId = result.workspace_id ?? effectiveWorkspaceId;

      set((s) => ({
        documents: s.documents.map((d) =>
          d.id === docId
            ? { ...d, id: actualId, status: 'processing' as DocumentStatus, workspaceId: actualWorkspaceId }
            : d
        ),
      }));

      await delay(300);
      await get().loadFromBackend(effectiveWorkspaceId ?? undefined);
      const list = await fetchWorkspaces(token).catch(() => []);
      useWorkspaceStore.getState().setCachedWorkspaces(list);

      const maxTime = 60000;
      const start = Date.now();
      const poll = async () => {
        if (Date.now() - start > maxTime) {
          set((s) => ({
            documents: s.documents.map((d) =>
              d.id === actualId ? { ...d, status: 'error' as DocumentStatus, errorMessage: 'Timeout' } : d
            ),
          }));
          return;
        }
        try {
          const res = await fetch(`${DOCUMENTS_API}/${actualId}/status`, {
            headers: { Authorization: `Bearer ${useAuthStore.getState().token}` },
          });
          if (!res.ok) {
            setTimeout(poll, 2000);
            return;
          }
          const data = await res.json();
          if (data.status === 'ready') {
            set((s) => ({
              documents: s.documents.map((d) =>
                d.id === actualId ? { ...d, status: 'ready' as DocumentStatus, chunkCount: data.chunkCount } : d
              ),
            }));
            return;
          }
          if (data.status === 'error') {
            set((s) => ({
              documents: s.documents.map((d) =>
                d.id === actualId
                  ? { ...d, status: 'error' as DocumentStatus, errorMessage: data.error || data.errorMessage }
                  : d
              ),
            }));
            return;
          }
        } catch {
          /* ignore */
        }
        setTimeout(poll, 1200);
      };
      setTimeout(poll, 800);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      set((state) => ({
        documents: state.documents.map((doc) =>
          doc.id === docId ? { ...doc, status: 'error' as DocumentStatus, errorMessage: msg } : doc
        ),
      }));
      throw err;
    } finally {
      set({ isUploading: false });
    }
  },

  deleteDocument: async (id: string) => {
    const token = useAuthStore.getState().token;
    if (!token) return;

    const previous = get().documents;
    set((s) => ({ documents: s.documents.filter((d) => d.id !== id) }));

    let deleted = false;
    try {
      const res = await fetch(`${DOCUMENTS_API}/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 404) {
        deleted = true; // already gone on server
      } else if (!res.ok) {
        throw new Error('Delete failed');
      } else {
        deleted = true;
      }
    } catch {
      // DELETE itself failed – roll back optimistic removal
      set({ documents: previous });
      throw new Error('Failed to delete');
    }

    if (deleted) {
      const wsId = useWorkspaceStore.getState().selectedWorkspaceId ?? useAuthStore.getState().user?.workspace_id;
      await get().loadFromBackend(wsId ?? undefined).catch(() => {});
      const list = await fetchWorkspaces(token).catch(() => []);
      useWorkspaceStore.getState().setCachedWorkspaces(list);
    }
  },

  updateDocumentStatus: (id, status, chunkCount) => {
    set((s) => ({
      documents: s.documents.map((d) => (d.id === id ? { ...d, status, chunkCount } : d)),
    }));
  },

  clearOnLogout: () =>
    set({ documents: [], isLoading: false, lastSyncError: null }),
}));

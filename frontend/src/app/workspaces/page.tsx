'use client';

import { useState, useEffect, useCallback, useRef, memo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/store/authStore';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { useChatStore } from '@/store/chatStore';
import { useDocumentStore } from '@/store/documentStore';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FolderOpen,
  Plus,
  Trash2,
  FileText,
  MoreVertical,
  Check,
  X,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import { cn, formatDate } from '@/lib/utils';
import { fetchWorkspaces, ApiError } from '@/lib/api';
import { toast } from '@/components/ui/Toaster';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';

interface Workspace {
  id: string;
  name: string;
  description?: string | null;
  documentCount: number;
  createdAt?: string;
  updatedAt?: string;
}

export default function WorkspacesPage() {
  const { cachedWorkspaces, setCachedWorkspaces, validateSelectedWorkspace, setSelectedWorkspaceId, setOwnerUserId } = useWorkspaceStore();
  const { documents, loadFromBackend } = useDocumentStore();
  const [workspaces, setWorkspaces] = useState<Workspace[]>(cachedWorkspaces);
  const [isLoading, setIsLoading] = useState(cachedWorkspaces.length === 0);
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const token = useAuthStore((s) => s.token);
  const authReady = useAuthStore((s) => s.hasHydrated);
  const currentUserId = useAuthStore((s) => s.user?.id ?? null);
  const currentDefaultWorkspace = useAuthStore((s) => s.user?.workspace_id ?? null);
  const isAuthenticated = authReady && Boolean(token);
  const router = useRouter();
  const [deleteConfirm, setDeleteConfirm] = useState<{ id: string; name: string } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadErrorStatus, setLoadErrorStatus] = useState<number | null>(null);

  // Single source of truth: doc count from document store so it matches Documents/Chat pages
  const getWorkspaceDocCount = useCallback(
    (workspaceId: string) =>
      documents.filter((d) => String(d.workspaceId ?? '') === String(workspaceId)).length,
    [documents]
  );

  const loadWorkspaces = useCallback(async (isRetry = false) => {
    if (!token) {
      setIsLoading(false);
      setLoadError(null);
      setLoadErrorStatus(null);
      return;
    }
    if (!isRetry) {
      setLoadError(null);
      setLoadErrorStatus(null);
    }
    try {
      const list = await fetchWorkspaces(token);
      setWorkspaces(list);
      setCachedWorkspaces(list);
      validateSelectedWorkspace(list);
      setOwnerUserId(currentUserId);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : null;
      if (status === 401) {
        setLoadErrorStatus(401);
        setLoadError('Your session may have expired. Please sign out and sign in again.');
        if (useWorkspaceStore.getState().cachedWorkspaces.length === 0) toast('error', 'Something went wrong. Please try again.');
      } else if (!isRetry) {
        await new Promise((r) => setTimeout(r, 1200));
        return loadWorkspaces(true);
      } else {
        setLoadErrorStatus(status ?? null);
        setLoadError('Couldn’t load workspaces. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [token, setCachedWorkspaces, validateSelectedWorkspace, currentUserId, setOwnerUserId]);

  useEffect(() => {
    if (!authReady) return;
    if (cachedWorkspaces.length > 0) {
      setWorkspaces(cachedWorkspaces);
      setIsLoading(false);
    }
    loadWorkspaces();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run on loadWorkspaces only; cache is for initial display
  }, [authReady, loadWorkspaces]);

  // Load all docs from backend so workspace counts are correct
  useEffect(() => {
    if (!token) return;
    loadFromBackend(undefined);
  }, [token, loadFromBackend]);

  const createWorkspace = async () => {
    if (!newName.trim()) return;
    if (!token) {
      toast('error', 'Please sign in before creating a workspace');
      return;
    }

    try {
      const headers: HeadersInit = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const response = await fetch('/api/workspaces', {
        method: 'POST',
        headers,
        body: JSON.stringify({ name: newName, description: newDescription }),
      });

      if (response.ok) {
        const workspace = await response.json();
        const next = [workspace, ...workspaces];
        setWorkspaces(next);
        setCachedWorkspaces(next);
        validateSelectedWorkspace(next);
        setNewName('');
        setNewDescription('');
        setIsCreating(false);
        toast('success', 'Workspace created');
      } else {
        const body = await response.json().catch(() => ({}));
        const message = body?.error ?? body?.detail ?? 'Failed to create workspace';
        toast('error', typeof message === 'string' ? message : 'Failed to create workspace');
      }
    } catch {
      toast('error', 'Failed to create workspace');
    }
  };

  const deleteWorkspace = async (id: string) => {
    try {
      const headers: HeadersInit = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const response = await fetch(`/api/workspaces/${id}`, {
        method: 'DELETE',
        headers,
      });
      if (response.ok) {
        useChatStore.getState().clearWorkspaceConversations(id);
        if (currentDefaultWorkspace === id) {
          useAuthStore.getState().setDefaultWorkspace(null);
        }
        if (useWorkspaceStore.getState().selectedWorkspaceId === id) {
          setSelectedWorkspaceId(null);
        }
        const list = await fetchWorkspaces(token);
        setWorkspaces(list);
        setCachedWorkspaces(list);
        validateSelectedWorkspace(list);
        const newDefault = list[0]?.id ?? null;
        if (currentDefaultWorkspace === id && newDefault) {
          await useAuthStore.getState().setDefaultWorkspace(newDefault);
        }
        if (useWorkspaceStore.getState().selectedWorkspaceId === id || !useWorkspaceStore.getState().selectedWorkspaceId) {
          setSelectedWorkspaceId(newDefault);
        }
        useDocumentStore.getState().loadFromBackend(undefined);
        toast('success', 'Workspace deleted');
      } else {
        const errBody = await response.json().catch(() => ({}));
        const msg = errBody?.detail ?? 'Failed to delete workspace';
        toast('error', typeof msg === 'string' ? msg : 'Failed to delete workspace');
      }
    } catch {
      toast('error', 'Failed to delete workspace');
    }
  };

  return (
    <div className="h-full overflow-hidden flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto min-h-0 scroll-region">
        <div className="max-w-5xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="page-title text-[1.45rem] sm:text-[1.65rem]">Workspaces</h1>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Organize documents into separate workspaces
            </p>
          </div>
          {!authReady ? (
            <div className="h-10 w-40 rounded-lg glass opacity-50" aria-hidden="true" />
          ) : isAuthenticated ? (
            <button
              onClick={() => setIsCreating(true)}
              className="btn btn-primary !py-2 !px-4 text-sm"
            >
              <Plus className="w-4 h-4" />
              New workspace
            </button>
          ) : (
            <Link
              href="/login"
              className="btn btn-secondary !py-2 !px-4 text-sm"
            >
              Sign in to create workspaces
            </Link>
          )}
        </div>

        {/* Create Form */}
        <AnimatePresence>
          {isCreating && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-6 overflow-hidden"
            >
              <div className="card p-4 sm:p-5">
                <div className="space-y-3">
                  <input
                    type="text"
                    placeholder="Workspace name"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="field"
                    autoFocus
                  />
                  <textarea
                    placeholder="Optional: what this workspace is for"
                    value={newDescription}
                    onChange={(e) => setNewDescription(e.target.value)}
                    className="field resize-none"
                    rows={2}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={createWorkspace}
                      disabled={!newName.trim()}
                      className="btn btn-primary !py-2 !px-4 text-sm"
                    >
                      <Check className="w-4 h-4" />
                      Create
                    </button>
                    <button
                      onClick={() => {
                        setIsCreating(false);
                        setNewName('');
                        setNewDescription('');
                      }}
                      className="btn btn-secondary !py-2 !px-4 text-sm"
                    >
                      <X className="w-4 h-4" />
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Workspaces Grid */}
        {isLoading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-32 rounded-xl glass animate-pulse" />
            ))}
          </div>
        ) : loadError ? (
          <div className="text-center py-12">
            <AlertCircle className="w-12 h-12 mx-auto text-amber-500 mb-3" />
            <p className="text-slate-700 dark:text-slate-300 font-medium">{loadError}</p>
            {loadErrorStatus === 401 ? (
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    useAuthStore.getState().logout();
                    router.push('/login');
                  }}
                  className="inline-flex px-4 py-2 glass text-slate-900 dark:text-slate-100 rounded-lg hover:bg-black/5 dark:hover:bg-white/8 text-sm font-medium"
                >
                  Sign out and sign in again
                </button>
                <Link
                  href="/login"
                  className="inline-flex px-4 py-2 glass text-slate-700 dark:text-slate-300 rounded-lg hover:bg-black/5 dark:hover:bg-white/8 text-sm font-medium"
                >
                  Go to login
                </Link>
              </div>
            ) : (
              <>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">If this keeps happening, try signing out and signing in again.</p>
                <button
                  type="button"
                  onClick={() => loadWorkspaces()}
                  className="inline-flex mt-4 px-4 py-2 glass text-slate-900 dark:text-slate-100 rounded-lg hover:bg-black/5 dark:hover:bg-white/8 text-sm font-medium"
                >
                  Try again
                </button>
              </>
            )}
          </div>
        ) : workspaces.length === 0 ? (
          <div className="text-center py-12">
            <FolderOpen className="w-12 h-12 mx-auto text-slate-400 dark:text-slate-600 mb-3" />
            <p className="text-slate-600 dark:text-slate-400">
              {authReady && isAuthenticated ? 'No workspaces yet' : 'Sign in to create and manage workspaces'}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {authReady && isAuthenticated
                ? 'Create a workspace to organize your documents'
                : 'Workspaces let you organize documents into separate collections'}
            </p>
            {authReady && !isAuthenticated && (
              <Link
                href="/login"
                className="inline-flex mt-4 px-4 py-2 glass text-slate-900 dark:text-slate-100 rounded-lg hover:bg-black/5 dark:hover:bg-white/8 text-sm font-medium"
              >
                Sign in
              </Link>
            )}
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <AnimatePresence mode="popLayout" initial={false}>
              {workspaces.map((workspace) => (
                <WorkspaceCard
                  key={workspace.id}
                  workspace={workspace}
                  docCount={getWorkspaceDocCount(workspace.id)}
                  isDefaultWorkspace={workspace.id === currentDefaultWorkspace || workspace.name === 'My workspace'}
                  onOpen={() => {
                    useWorkspaceStore.getState().setSelectedWorkspaceId(workspace.id);
                    router.push(`/documents?workspace=${encodeURIComponent(workspace.id)}`);
                  }}
                  onDeleteRequest={() => setDeleteConfirm({ id: workspace.id, name: workspace.name })}
                />
              ))}
            </AnimatePresence>
          </div>
        )}

        <ConfirmDialog
          open={!!deleteConfirm}
          title="Delete workspace"
          message={
            deleteConfirm
              ? `Are you sure you want to delete "${deleteConfirm.name}"? Documents in this workspace will remain but will be unassigned.`
              : ''
          }
          confirmLabel="Delete"
          onConfirm={() => {
            if (deleteConfirm) {
              deleteWorkspace(deleteConfirm.id);
              setDeleteConfirm(null);
            }
          }}
          onCancel={() => setDeleteConfirm(null)}
        />
        </div>
      </div>
    </div>
  );
}

interface WorkspaceCardProps {
  workspace: Workspace;
  docCount: number;
  isDefaultWorkspace: boolean;
  onOpen: () => void;
  onDeleteRequest: () => void;
}

const WorkspaceCard = memo(function WorkspaceCard({
  workspace,
  docCount,
  isDefaultWorkspace,
  onOpen,
  onDeleteRequest,
}: WorkspaceCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!showMenu) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showMenu]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.15 }}
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onOpen()}
      className={cn(
        'group relative p-4 item-row cursor-pointer'
      )}
    >
      {/* Icon */}
      <div className="w-10 h-10 rounded-lg glass flex items-center justify-center mb-3">
        <FolderOpen className="w-5 h-5 text-sky-700 dark:text-sky-400" />
      </div>

      {/* Content */}
      <div className="flex items-center gap-2 min-w-0">
        <h3 className="font-medium text-slate-900 dark:text-slate-100 truncate">{workspace.name}</h3>
        {isDefaultWorkspace && (
          <span className="shrink-0 text-xs font-medium text-slate-600 dark:text-slate-400 glass px-1.5 py-0.5 rounded" title="Default workspace (cannot be deleted)">
            Default
          </span>
        )}
      </div>
      {workspace.description && (
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1 line-clamp-2">
          {workspace.description}
        </p>
      )}

      {/* Stats */}
      <div className="flex items-center gap-3 mt-3 text-xs text-slate-500 dark:text-slate-400">
        <span className="flex items-center gap-1">
          <FileText className="w-3 h-3" />
          {docCount} docs
        </span>
        {workspace.updatedAt && (
          <span>Updated {formatDate(workspace.updatedAt)}</span>
        )}
      </div>

      {/* Menu - hide for default "My workspace" (cannot be deleted) */}
      {!isDefaultWorkspace && (
        <div className="absolute top-3 right-3" ref={menuRef}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowMenu(!showMenu);
            }}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-black/5 dark:hover:bg-white/8 opacity-0 group-hover:opacity-100 transition-all"
          >
            <MoreVertical className="w-4 h-4" />
          </button>

          {showMenu && (
            <div className="absolute right-0 mt-1 w-32 py-1 glass rounded-lg shadow-xl z-10">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteRequest();
                  setShowMenu(false);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 hover:bg-black/5 dark:hover:bg-white/8"
              >
                <Trash2 className="w-4 h-4" />
                Delete
              </button>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
});

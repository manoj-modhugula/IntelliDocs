'use client';

import { useState, useCallback, useEffect, useRef, memo, useMemo } from 'react';
import { useSearchParams, usePathname } from 'next/navigation';
import { useDropzone } from 'react-dropzone';
import { useDebounce } from '@/lib/useDebounce';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  Upload,
  FileText,
  Trash2,
  Search,
  CheckCircle,
  Clock,
  AlertCircle,
  RefreshCw,
  X,
  File,
  FolderOpen,
} from 'lucide-react';
import { useDocumentStore, Document, DocumentStatus } from '@/store/documentStore';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { useAuthStore } from '@/store/authStore';
import { cn, formatFileSize, formatDate } from '@/lib/utils';
import { fetchWorkspaces } from '@/lib/api';
import type { CachedWorkspace } from '@/store/workspaceStore';
import { toast } from '@/components/ui/Toaster';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';

export default function DocumentsPage() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const [searchQuery, setSearchQuery] = useState('');
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<{ id: string; name: string } | null>(null);
  const { cachedWorkspaces, setCachedWorkspaces, validateSelectedWorkspace, setOwnerUserId, selectedWorkspaceId, setSelectedWorkspaceId } = useWorkspaceStore();
  const [workspaces, setWorkspaces] = useState<CachedWorkspace[]>(() => cachedWorkspaces);
  const workspaceFromUrl = searchParams.get('workspace');

  const { documents, uploadDocument, deleteDocument, isUploading, isLoading, loadFromBackend } = useDocumentStore();
  const token = useAuthStore((s) => s.token);
  const userWorkspaceId = useAuthStore((s) => s.user?.workspace_id ?? null);
  const currentUserId = useAuthStore((s) => s.user?.id ?? null);

  const effectiveWorkspaceId =
    workspaceFromUrl || selectedWorkspaceId || userWorkspaceId || undefined;

  // When opened from Workspaces with ?workspace=id, set selection
  useEffect(() => {
    if (workspaceFromUrl) setSelectedWorkspaceId(workspaceFromUrl);
  }, [searchParams, workspaceFromUrl, setSelectedWorkspaceId]);

  // Default to user's "My workspace" when none selected
  useEffect(() => {
    if (!token) return;
    useWorkspaceStore.getState().setDefaultFromUser(useAuthStore.getState().user?.workspace_id);
  }, [token]);

  // Always load workspaces from backend when we need them (no cache)
  useEffect(() => {
    if (!token) return;
    fetchWorkspaces(token)
      .then((list) => {
        setWorkspaces(list);
        setCachedWorkspaces(list);
        validateSelectedWorkspace(list);
        setOwnerUserId(currentUserId);
        if (list.length > 0 && !selectedWorkspaceId) setSelectedWorkspaceId(list[0].id);
      })
      .catch(() => {});
  }, [token, setCachedWorkspaces, validateSelectedWorkspace, setOwnerUserId, currentUserId, setSelectedWorkspaceId, selectedWorkspaceId]);

  useEffect(() => {
    if (cachedWorkspaces.length > 0) setWorkspaces(cachedWorkspaces);
  }, [cachedWorkspaces]);

  // Always load documents from backend when on this page (no cache – server is source of truth)
  useEffect(() => {
    if (pathname !== '/documents' || !token || !effectiveWorkspaceId) return;
    loadFromBackend(effectiveWorkspaceId);
  }, [pathname, token, effectiveWorkspaceId, loadFromBackend]);

  // When tab becomes visible again, reload from backend
  useEffect(() => {
    if (!token || !effectiveWorkspaceId) return;
    const onVisible = () => {
      if (document.visibilityState === 'visible') loadFromBackend(effectiveWorkspaceId);
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [token, effectiveWorkspaceId, loadFromBackend]);

  // Poll while any doc is processing
  const hasProcessing = documents.some((d) => d.status === 'processing' || d.status === 'pending');
  useEffect(() => {
    if (!hasProcessing || !effectiveWorkspaceId) return;
    const id = setInterval(() => loadFromBackend(effectiveWorkspaceId), 4000);
    return () => clearInterval(id);
  }, [hasProcessing, effectiveWorkspaceId, loadFromBackend]);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const wsId =
      (workspaceFromUrl || selectedWorkspaceId || useAuthStore.getState().user?.workspace_id || workspaces[0]?.id) ?? undefined;
    for (const file of acceptedFiles) {
      try {
        await uploadDocument(file, wsId);
        toast('success', `${file.name} uploaded successfully`);
        // Refresh workspace list so doc count updates (backend cache invalidated on upload)
        const token = useAuthStore.getState().token;
        if (token) {
          fetchWorkspaces(token).then((list) => setCachedWorkspaces(list)).catch(() => {});
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Upload failed';
        toast('error', msg.includes('Upload failed') ? `Failed to upload ${file.name}` : msg);
      }
    }
  }, [uploadDocument, workspaceFromUrl, selectedWorkspaceId, workspaces, setCachedWorkspaces]);

  const onDropRejected = useCallback((rejections: any[]) => {
    rejections.forEach((rejection) => {
      const fileName = rejection?.file?.name || 'File';
      const err = rejection?.errors?.[0];
      const msg =
        err?.code === 'file-too-large'
          ? 'File too large (max 50MB)'
          : err?.code === 'file-invalid-type'
            ? 'Unsupported file type (PDF, DOC, DOCX, TXT, MD)'
            : err?.message || 'File not accepted';
      toast('error', `${fileName}: ${msg}`);
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    onDropRejected,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
    },
    maxSize: 50 * 1024 * 1024,
    disabled: isUploading,
  });

  const debouncedSearch = useDebounce(searchQuery, 150);
  // Strict: only docs for the effective workspace (selected or default "My workspace")
  const scopedDocuments = useMemo(() => {
    const wsId = effectiveWorkspaceId ?? '';
    if (!wsId) return [];
    return documents.filter((doc) => String(doc.workspaceId ?? '') === String(wsId));
  }, [documents, effectiveWorkspaceId]);
  const filteredDocuments = useMemo(() => {
    return scopedDocuments.filter((doc) =>
      doc.name.toLowerCase().includes(debouncedSearch.toLowerCase())
    );
  }, [scopedDocuments, debouncedSearch]);

  const selectedWorkspaceName = useMemo(() => {
    if (!effectiveWorkspaceId) return null;
    return workspaces.find((w) => w.id === effectiveWorkspaceId)?.name ?? null;
  }, [effectiveWorkspaceId, workspaces]);
  // Single source of truth: selected workspace count = length of list we actually show; others = API count
  const getWorkspaceDisplayCount = useCallback(
    (w: CachedWorkspace) =>
      w.id === effectiveWorkspaceId ? scopedDocuments.length : (w.documentCount ?? 0),
    [effectiveWorkspaceId, scopedDocuments.length]
  );
  const isSearching = debouncedSearch.trim().length > 0;
  const activeDocuments = filteredDocuments;

  const handleDelete = async (id: string, name: string) => {
    setIsDeleting(id);
    setDeleteConfirm(null);
    try {
      await deleteDocument(id);
      toast('success', `${name} deleted`);
      // Refetch workspaces so dropdown count matches DB (backend counts docs live)
      const token = useAuthStore.getState().token;
      if (token) fetchWorkspaces(token).then((list) => setCachedWorkspaces(list)).catch(() => {});
    } catch {
      toast('error', 'Failed to delete document');
    } finally {
      setIsDeleting(null);
    }
  };

  const readyCount = activeDocuments.filter((d) => d.status === 'ready').length;
  const processingCount = activeDocuments.filter((d) => d.status === 'processing').length;

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header - F-pattern: title left, status right */}
      <div className="flex-shrink-0 border-b border-white/20 dark:border-white/10 px-4 sm:px-6 py-3 sm:py-4 glass">
        <div className="max-w-5xl mx-auto">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-1">
            <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Documents</h1>
            <div className="flex items-center gap-3 text-sm">
              {readyCount > 0 && (
                <span className="flex items-center gap-1.5 text-slate-900 dark:text-slate-100">
                  <CheckCircle className="w-4 h-4" />
                  {readyCount} ready
                </span>
              )}
              {processingCount > 0 && (
                <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  {processingCount} processing
                </span>
              )}
            </div>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Upload documents to ask questions about them
          </p>
          {/* Workspace filter */}
          {workspaces.length > 0 && (
            <div className="mt-3 flex flex-col sm:flex-row sm:items-center gap-2">
              <FolderOpen className="w-4 h-4 text-slate-500 dark:text-slate-400" />
              <select
                value={effectiveWorkspaceId ?? ''}
                onChange={(e) => setSelectedWorkspaceId(e.target.value || null)}
                className="rounded-lg glass-input text-slate-900 dark:text-slate-100 text-sm px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-slate-400/50 dark:focus:ring-slate-500/50"
                aria-label="Filter documents by workspace"
                title="Only docs in this workspace are shown. Uploads go here."
              >
                {workspaces.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name} ({getWorkspaceDisplayCount(w)})
                  </option>
                ))}
              </select>
              <span className="text-xs text-slate-500 dark:text-slate-400 hidden sm:inline">
                Only docs in &quot;{selectedWorkspaceName ?? 'workspace'}&quot; are shown. Uploads go here.
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 scroll-region">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* Upload Zone */}
          <div
            {...getRootProps({
              'aria-label': 'Upload documents: drag files here or click to browse. PDF, DOCX, TXT, MD up to 50MB.',
            })}
            className={cn(
              'relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200 glass-card',
              isDragActive && !isDragReject && 'border-white/50 dark:border-white/30',
              isDragReject && 'border-white/40 dark:border-white/20',
              !isDragActive && 'border-white/30 dark:border-white/15 hover:border-white/40 dark:hover:border-white/25',
              isUploading && 'pointer-events-none opacity-60'
            )}
          >
            <input {...getInputProps()} aria-hidden />
            
            <div className="space-y-3">
              <div className={cn(
                'w-12 h-12 mx-auto rounded-xl flex items-center justify-center transition-colors glass',
                isDragActive ? 'text-slate-900 dark:text-slate-100' : 'text-slate-500 dark:text-slate-400'
              )}>
                {isUploading ? (
                  <RefreshCw className="w-6 h-6 text-slate-700 animate-spin" />
                ) : (
                  <Upload className={cn('w-6 h-6', isDragActive ? 'text-slate-900' : 'text-slate-500')} />
                )}
              </div>
              
              <div>
                <p className="font-medium text-slate-900 dark:text-slate-100">
                  {isUploading ? 'Uploading...' : isDragActive ? 'Drop files here' : 'Drop files or click to upload'}
                </p>
                <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  PDF, DOCX, TXT, MD (up to 50MB)
                </p>
              </div>
            </div>
          </div>

          {/* Search */}
          {documents.length > 0 && (
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 dark:text-slate-400" />
              <input
                type="text"
                placeholder="Search documents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search documents by name"
                className="w-full pl-10 pr-4 py-2.5 rounded-lg glass-input text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400/50 dark:focus:ring-slate-500/50 text-sm"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          )}

          {/* Documents List – always from backend */}
          {isLoading ? (
            <div className="text-center py-12">
              <RefreshCw className="w-10 h-10 mx-auto text-slate-400 mb-3 animate-spin" />
              <p className="text-slate-600 dark:text-slate-400 text-sm">Loading documents…</p>
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div className="text-center py-12">
              <File className="w-12 h-12 mx-auto text-slate-400 dark:text-slate-600 mb-3" />
              <p className="text-slate-600 dark:text-slate-400 text-sm">
                {isSearching
                  ? 'No documents match your search'
                  : selectedWorkspaceName
                    ? `No documents in "${selectedWorkspaceName}" yet`
                    : 'No documents uploaded yet'}
              </p>
              {!isSearching && selectedWorkspaceName && (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Upload while this workspace is selected to keep documents grouped.
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <AnimatePresence mode="popLayout" initial={false}>
                {filteredDocuments.map((doc) => (
                  <DocumentRow
                    key={doc.id}
                    document={doc}
                    workspaceName={workspaces.find((w) => w.id === doc.workspaceId)?.name}
                    isDeleting={isDeleting === doc.id}
                    onDeleteRequest={() => setDeleteConfirm({ id: doc.id, name: doc.name })}
                  />
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete document"
        message={
          deleteConfirm
            ? `Are you sure you want to delete "${deleteConfirm.name}"? This cannot be undone.`
            : ''
        }
        confirmLabel="Delete"
        onConfirm={() => {
          if (deleteConfirm) handleDelete(deleteConfirm.id, deleteConfirm.name);
        }}
        onCancel={() => setDeleteConfirm(null)}
      />
    </div>
  );
}

interface DocumentRowProps {
  document: Document;
  workspaceName?: string;
  isDeleting: boolean;
  onDeleteRequest: () => void;
}

const DocumentRow = memo(function DocumentRow({ document, workspaceName, isDeleting, onDeleteRequest }: DocumentRowProps) {
  const prefersReducedMotion = useReducedMotion();
  const statusConfig: Record<DocumentStatus, { icon: typeof Clock; color: string; label: string; animate?: boolean }> = {
    pending: { icon: Clock, color: 'text-slate-500', label: 'Pending' },
    processing: { icon: RefreshCw, color: 'text-slate-500', label: 'Processing', animate: true },
    ready: { icon: CheckCircle, color: 'text-emerald-600', label: 'Ready' },
    error: { icon: AlertCircle, color: 'text-rose-600', label: 'Error' },
  };

  const status = statusConfig[document.status as DocumentStatus];
  const StatusIcon = status.icon;

  const getFileEmoji = (type: string) => {
    if (type.includes('pdf')) return '📄';
    if (type.includes('word') || type.includes('document')) return '📝';
    return '📃';
  };

  const motionProps = prefersReducedMotion
    ? { layout: false }
    : {
        layout: true,
        initial: { opacity: 0, y: 6 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.12 },
        exit: { opacity: 0, x: -20 },
      };

  return (
    <motion.div
      {...motionProps}
      className={cn(
        'group flex items-center gap-4 p-4 rounded-xl glass-card',
        'hover:bg-black/5 dark:hover:bg-white/8 transition-all'
      )}
    >
      {/* Icon */}
      <span className="text-2xl">{getFileEmoji(document.type)}</span>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <h3 className="font-medium text-slate-900 dark:text-slate-100 truncate" title={document.name}>
          {document.name}
        </h3>
        <div className="flex items-center gap-3 mt-1 text-xs text-slate-500 flex-wrap">
          <span>{formatFileSize(document.size)}</span>
          <span>•</span>
          <span>{formatDate(document.uploadedAt)}</span>
          {workspaceName && (
            <>
              <span>•</span>
              <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                <FolderOpen className="w-3 h-3" />
                {workspaceName}
              </span>
            </>
          )}
          {document.chunkCount && (
            <>
              <span>•</span>
              <span>{document.chunkCount} chunks</span>
            </>
          )}
        </div>
        {document.status === 'error' && document.errorMessage && (
          <p className="mt-1 text-xs text-rose-600 dark:text-rose-400 truncate" title={document.errorMessage}>
            {document.errorMessage}
          </p>
        )}
      </div>

      {/* Status */}
      <div className={cn('flex items-center gap-1.5 text-sm', status.color)}>
        <StatusIcon className={cn('w-4 h-4', status.animate && 'animate-spin')} />
        <span>{status.label}</span>
      </div>

      {/* Delete - always visible when deleting, otherwise on hover */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDeleteRequest();
        }}
        disabled={isDeleting}
        aria-label={`Delete ${document.name}`}
        className={cn(
          'p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-black/5 dark:hover:bg-white/8 transition-all shrink-0',
          'opacity-0 group-hover:opacity-100',
          isDeleting && 'opacity-100'
        )}
      >
        {isDeleting ? (
          <RefreshCw className="w-4 h-4 animate-spin" />
        ) : (
          <Trash2 className="w-4 h-4" />
        )}
      </button>
    </motion.div>
  );
});

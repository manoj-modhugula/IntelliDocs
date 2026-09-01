'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Settings, Trash2, HardDrive, FolderOpen, Check, Sun, Moon, Pencil, X, Plus, MessageSquare } from 'lucide-react';
import { useDocumentStore } from '@/store/documentStore';
import { useChatStore } from '@/store/chatStore';
import { useAuthStore } from '@/store/authStore';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { useThemeStore } from '@/store/themeStore';
import { toast } from '@/components/ui/Toaster';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { cn, formatFileSize } from '@/lib/utils';
import { fetchWorkspaces, fetchSkills, createSkill, updateSkill, deleteSkill, type SkillItem } from '@/lib/api';

export default function SettingsPage() {
  const { documents } = useDocumentStore();
  const { conversations } = useChatStore();
  const { user, token, setDefaultWorkspace } = useAuthStore();
  const { setSelectedWorkspaceId, cachedWorkspaces, setCachedWorkspaces } = useWorkspaceStore();
  const { theme, toggleTheme } = useThemeStore();
  const [isClearing, setIsClearing] = useState(false);
  const [workspaces, setWorkspaces] = useState<{ id: string; name: string; documentCount: number }[]>(cachedWorkspaces);
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [addName, setAddName] = useState('');
  const [addAction, setAddAction] = useState('');
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editAction, setEditAction] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [clearDataConfirmOpen, setClearDataConfirmOpen] = useState(false);

  useEffect(() => {
    if (cachedWorkspaces.length > 0) setWorkspaces(cachedWorkspaces);
  }, [cachedWorkspaces]);

  useEffect(() => {
    if (!token) return;
    if (cachedWorkspaces.length > 0) setWorkspaces(cachedWorkspaces);
    fetchWorkspaces(token)
      .then((list) => {
        setWorkspaces(list);
        setCachedWorkspaces(list);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run on token only; cache is for initial display
  }, [token, setCachedWorkspaces]);

  const loadSkills = useCallback(async () => {
    if (!token) return;
    setSkillsLoading(true);
    try {
      const list = await fetchSkills(token);
      setSkills(list);
    } catch {
      toast('error', 'Failed to load skills');
    } finally {
      setSkillsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadSkills();
  }, [loadSkills]);

  const handleAddSkill = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = addName.trim().toLowerCase().replace(/\s+/g, '_');
    const action = addAction.trim();
    if (!name || !action || !token) return;
    setAdding(true);
    try {
      await createSkill(token, { name, action });
      setAddName('');
      setAddAction('');
      await loadSkills();
      toast('success', `Skill /${name} created`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create skill';
      toast('error', msg);
    } finally {
      setAdding(false);
    }
  };

  const startEdit = (s: SkillItem) => {
    setEditingId(s.id);
    setEditName(s.name);
    setEditAction(s.action);
  };

  const handleUpdateSkill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingId || !token) return;
    const name = editName.trim().toLowerCase().replace(/\s+/g, '_');
    const action = editAction.trim();
    if (!name || !action) return;
    try {
      await updateSkill(token, editingId, { name, action });
      setEditingId(null);
      await loadSkills();
      toast('success', 'Skill updated');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update skill';
      toast('error', msg);
    }
  };

  const handleDeleteSkill = async (id: string) => {
    if (!token) return;
    setDeletingId(id);
    try {
      await deleteSkill(token, id);
      await loadSkills();
      toast('success', 'Skill deleted');
    } catch {
      toast('error', 'Failed to delete skill');
    } finally {
      setDeletingId(null);
    }
  };

  const clearAllData = () => {
    setIsClearing(true);
    try {
      useDocumentStore.getState().clearOnLogout();
      useChatStore.getState().clearOnLogout();
      useWorkspaceStore.getState().clearOnLogout();
      useAuthStore.getState().logout();
      localStorage.removeItem('intellidocs-documents');
      localStorage.removeItem('intellidocs-chat');
      localStorage.removeItem('intellidocs-auth');
      localStorage.removeItem('intellidocs-workspace');
      toast('success', 'All local data cleared');
      setTimeout(() => window.location.reload(), 500);
    } catch {
      toast('error', 'Failed to clear data');
    } finally {
      setIsClearing(false);
    }
  };

  const totalSize = documents.reduce((acc, d) => acc + d.size, 0);
  const getWorkspaceDocCount = (workspaceId: string) =>
    documents.filter((d) => {
      const docWs = d.workspaceId ?? null;
      if (String(workspaceId) === String(docWs)) return true;
      if (!docWs && user?.workspace_id && String(workspaceId) === String(user.workspace_id)) return true;
      return false;
    }).length;

  return (
    <div className="h-full overflow-hidden flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto min-h-0 scroll-region">
        <div className="max-w-2xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-lg glass flex items-center justify-center">
            <Settings className="w-5 h-5 text-sky-700 dark:text-sky-400" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Settings</h1>
            <p className="text-sm text-slate-600 dark:text-slate-400">Manage your data</p>
          </div>
        </div>

        {/* Appearance */}
        <section className="mb-8">
          <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4">Appearance</h2>
          <div className="glass-card rounded-xl p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {theme === 'dark' ? (
                  <Moon className="w-5 h-5 text-indigo-500" />
                ) : (
                  <Sun className="w-5 h-5 text-amber-500" />
                )}
                <div>
                  <p className="font-medium text-slate-900 dark:text-slate-100">
                    {theme === 'dark' ? 'Dark mode' : 'Light mode'}
                  </p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Switch between light and dark themes
                  </p>
                </div>
              </div>
              <button
                onClick={toggleTheme}
                className={cn(
                  'relative w-12 h-7 rounded-full transition-colors duration-200',
                  theme === 'dark' ? 'bg-indigo-600' : 'bg-slate-300'
                )}
                aria-label="Toggle dark mode"
              >
                <span
                  className={cn(
                    'absolute top-0.5 left-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform duration-200',
                    theme === 'dark' ? 'translate-x-5' : 'translate-x-0'
                  )}
                />
              </button>
            </div>
          </div>
        </section>

        {/* Workspace (default) */}
        {user && workspaces.length > 0 && (
          <section className="mb-8">
            <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4">Default workspace</h2>
            <div className="glass-card rounded-xl p-4">
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                New uploads and chat use this workspace by default. On Documents and Chat, choosing &quot;Default workspace&quot; shows this workspace&apos;s files.
              </p>
              <div className="flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-slate-500 dark:text-slate-400 shrink-0" />
                <select
                  value={
                    workspaces.some((w) => w.id === user.workspace_id)
                      ? (user.workspace_id ?? '')
                      : (workspaces[0]?.id ?? '')
                  }
                  onChange={async (e) => {
                    const id = e.target.value;
                    if (!id) return;
                    await setDefaultWorkspace(id);
                    setSelectedWorkspaceId(id);
                    const w = workspaces.find((x) => x.id === id);
                    toast('success', w ? `"${w.name}" set as default workspace` : 'Default workspace updated');
                  }}
                  className={cn(
                    'flex-1 min-w-0 max-w-md px-3 py-2.5 rounded-lg text-sm font-medium glass-input text-slate-900 dark:text-slate-100',
                    'focus:outline-none focus:ring-2 focus:ring-sky-300 dark:focus:ring-sky-700 focus:border-sky-400 dark:focus:border-sky-600',
                    'hover:border-slate-300 dark:hover:border-slate-600 transition-colors'
                  )}
                >
                  {workspaces.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name} ({getWorkspaceDocCount(w.id)} docs)
                    </option>
                  ))}
                </select>
                <span className="shrink-0 flex items-center gap-1 text-xs text-sky-600 dark:text-sky-400 font-medium">
                  <Check className="w-3.5 h-3.5" />
                  Default
                </span>
              </div>
            </div>
          </section>
        )}

        {/* Skills (chat slash-commands) */}
        {user && (
          <section className="mb-8">
            <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4">Skills</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
              Use <code className="info-pill text-xs">/name</code> in chat to apply a skill. In Chat, type <code className="info-pill text-xs">/name</code> at the start of a message (e.g. <code className="info-pill text-xs">/short</code>).
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">
              <Link href="/chat" className="inline-flex items-center gap-1.5 text-sky-600 dark:text-sky-400 hover:underline">
                <MessageSquare className="w-4 h-4" />
                Open Chat
              </Link>
            </p>
            <div className="glass-card rounded-xl p-4 space-y-4">
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">Built-in</p>
              <ul className="space-y-1.5 mb-4">
                <li className="flex items-center gap-2 rounded-lg p-2 info-row text-slate-600 dark:text-slate-400">
                  <span className="font-medium text-slate-700 dark:text-slate-300">/short</span>
                  <span className="text-sm">Short, direct answer without extra explanation</span>
                </li>
              </ul>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">Create additional skills below. Names must be unique.</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">Your skills</p>
              {skillsLoading ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">Loading skills...</p>
              ) : (
                <ul className="space-y-2">
                  {skills.map((s) => (
                    <li key={s.id} className="flex items-start gap-2 rounded-lg p-2 info-row">
                      {editingId === s.id ? (
                        <form onSubmit={handleUpdateSkill} className="flex-1 min-w-0 flex flex-col sm:flex-row gap-2">
                          <input
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            placeholder="Name (slug)"
                            className="flex-1 min-w-0 px-2.5 py-1.5 rounded-lg text-sm glass-input text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400"
                          />
                          <input
                            value={editAction}
                            onChange={(e) => setEditAction(e.target.value)}
                            placeholder="LLM instruction"
                            className="flex-1 min-w-0 px-2.5 py-1.5 rounded-lg text-sm glass-input text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400"
                          />
                          <div className="flex gap-1">
                            <button type="submit" className="p-1.5 rounded-lg hover:bg-black/[0.05] dark:hover:bg-white/[0.08] text-emerald-600 dark:text-emerald-400" aria-label="Save">
                              <Check className="w-4 h-4" />
                            </button>
                            <button type="button" onClick={() => setEditingId(null)} className="p-1.5 rounded-lg hover:bg-black/[0.05] dark:hover:bg-white/[0.08] text-slate-500 dark:text-slate-400" aria-label="Cancel">
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        </form>
                      ) : (
                        <>
                          <span className="shrink-0 font-medium text-slate-900 dark:text-slate-100">/{s.name}</span>
                          <span className="flex-1 min-w-0 text-sm text-slate-600 dark:text-slate-400 truncate" title={s.action}>{s.action}</span>
                          <div className="flex gap-1 shrink-0">
                            <button type="button" onClick={() => startEdit(s)} className="p-1.5 rounded-lg hover:bg-black/[0.05] dark:hover:bg-white/[0.08] text-slate-500 dark:text-slate-400" aria-label="Edit">
                              <Pencil className="w-4 h-4" />
                            </button>
                            <button type="button" onClick={() => handleDeleteSkill(s.id)} disabled={deletingId === s.id} className="p-1.5 rounded-lg hover:bg-black/[0.05] dark:hover:bg-white/[0.08] text-rose-500 dark:text-rose-400 disabled:opacity-50" aria-label="Delete">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-xs text-slate-500 dark:text-slate-400 pt-2 border-t border-white/10 dark:border-white/5">
                Name becomes the slash command (e.g. <code className="info-pill">brief</code> → <code className="info-pill">/brief</code>). Use lowercase; spaces turn into underscores.
              </p>
              <form onSubmit={handleAddSkill} className="flex flex-col sm:flex-row gap-2 pt-2">
                <input
                  value={addName}
                  onChange={(e) => setAddName(e.target.value)}
                  placeholder="Name (e.g. short)"
                  aria-label="Skill name (slash command)"
                  className="flex-1 min-w-0 px-2.5 py-1.5 rounded-lg text-sm glass-input text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400"
                  />
                <input
                  value={addAction}
                  onChange={(e) => setAddAction(e.target.value)}
                  placeholder="LLM instruction (e.g. Give a short response)"
                  aria-label="Skill instruction for the model"
                  className="flex-1 min-w-0 px-2.5 py-1.5 rounded-lg text-sm glass-input text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400"
                />
                <button type="submit" disabled={adding || !addName.trim() || !addAction.trim()} className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium glass text-sky-700 dark:text-sky-300 hover:bg-black/[0.05] dark:hover:bg-white/[0.08] disabled:opacity-50 shrink-0">
                  <Plus className="w-4 h-4" />
                  {adding ? 'Adding...' : 'Add skill'}
                </button>
              </form>
            </div>
          </section>
        )}

        {/* Storage Info */}
        <section className="mb-8">
          <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4">Storage</h2>
          <div className="glass-card rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <HardDrive className="w-5 h-5 text-slate-500 dark:text-slate-400" />
                <span className="text-slate-900 dark:text-slate-100">Documents</span>
              </div>
              <div className="text-sm text-slate-600 dark:text-slate-400" title="Total across all workspaces">
                {documents.length} files ({formatFileSize(totalSize)})
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Settings className="w-5 h-5 text-slate-500 dark:text-slate-400" />
                <span className="text-slate-900 dark:text-slate-100">Conversations</span>
              </div>
              <div className="text-sm text-slate-600 dark:text-slate-400">
                {conversations.length} chats
              </div>
            </div>
          </div>
        </section>

        {/* Danger Zone */}
        <section>
          <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4">Danger Zone</h2>
          <div className="glass-card rounded-xl p-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-900 dark:text-slate-100">Clear all local data</p>
                <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  Clears only this device: your login, cached workspaces, document list, and chat history in this browser. Your account and all data on the server (workspaces, documents) are not deleted. Other users are not affected.
                </p>
              </div>
              <button
                onClick={() => setClearDataConfirmOpen(true)}
                disabled={isClearing}
                className={cn(
                  'flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium',
                  'glass text-rose-600 dark:text-rose-400 border border-rose-300/50 dark:border-rose-700/50 hover:bg-rose-500/[0.08] transition-[color,background-color] duration-150 disabled:opacity-50',
                  'shrink-0 whitespace-nowrap'
                )}
              >
                <Trash2 className="w-4 h-4 shrink-0" />
                {isClearing ? 'Clearing...' : 'Clear Data'}
              </button>
            </div>
          </div>
        </section>

        <ConfirmDialog
          open={clearDataConfirmOpen}
          title="Clear all local data?"
          message="This will clear login, cached workspaces, document list, and chat history on this device only. Your account and server data (workspaces, documents) are not deleted. The page will reload after clearing."
          confirmLabel="Clear data"
          cancelLabel="Cancel"
          variant="danger"
          onConfirm={() => {
            setClearDataConfirmOpen(false);
            clearAllData();
          }}
          onCancel={() => setClearDataConfirmOpen(false)}
        />

        {/* Version Info */}
        <div className="mt-12 text-center text-xs text-slate-500 dark:text-slate-400">
          <p>IntelliDocs v1.0.0</p>
          <p className="mt-1">Powered by AWS Bedrock + Next.js 14</p>
        </div>
        </div>
      </div>
    </div>
  );
}

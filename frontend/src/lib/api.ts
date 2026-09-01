/**
 * Shared API fetchers with request deduplication.
 * In-flight requests for the same endpoint share one promise.
 */
import { fetchWithDedup } from './fetchDedup';

export interface WorkspaceItem {
  id: string;
  name: string;
  description?: string | null;
  documentCount: number;
  createdAt?: string;
  updatedAt?: string;
}

const WORKSPACES_KEY = 'workspaces:list';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function fetchDocumentFile(
  token: string | null,
  documentId: string
): Promise<{ blob: Blob; contentType: string }> {
  const headers: HeadersInit = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`/api/documents/${documentId}/file`, {
    headers,
    cache: 'no-store',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message =
      typeof body?.error === 'string' ? body.error : 'Original file is not available';
    throw new ApiError(message, res.status);
  }
  const contentType = res.headers.get('Content-Type') || 'application/octet-stream';
  return { blob: await res.blob(), contentType };
}

export async function fetchWorkspaces(token: string | null): Promise<WorkspaceItem[]> {
  if (!token) return [];
  const headers: HeadersInit = { Authorization: `Bearer ${token}` };
  const res = await fetchWithDedup('/api/workspaces', { headers, keepalive: true, cache: 'no-store' }, WORKSPACES_KEY);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message = typeof body?.error === 'string' ? body.error : 'Failed to load workspaces';
    throw new ApiError(message, res.status);
  }
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

// --- Skills (chat slash-commands) ------------------------------------------──

export interface SkillItem {
  id: string;
  name: string;
  action: string;
  createdAt?: string | null;
  updatedAt?: string | null;
}

const SKILLS_KEY = 'skills:list';

export async function fetchSkills(token: string | null): Promise<SkillItem[]> {
  if (!token) return [];
  const res = await fetchWithDedup(
    '/api/skills',
    { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' },
    SKILLS_KEY
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = typeof body?.error === 'string' ? body.error : typeof body?.detail === 'string' ? body.detail : 'Failed to load skills';
    throw new ApiError(msg, res.status);
  }
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function createSkill(
  token: string,
  body: { name: string; action: string }
): Promise<SkillItem> {
  const res = await fetch('/api/skills', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const resBody = await res.json().catch(() => ({}));
    const msg = typeof resBody?.error === 'string' ? resBody.error : typeof resBody?.detail === 'string' ? resBody.detail : 'Failed to create skill';
    throw new ApiError(msg, res.status);
  }
  return res.json();
}

export async function updateSkill(
  token: string,
  skillId: string,
  body: { name?: string; action?: string }
): Promise<SkillItem> {
  const res = await fetch(`/api/skills/${skillId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const resBody = await res.json().catch(() => ({}));
    const msg = typeof resBody?.error === 'string' ? resBody.error : typeof resBody?.detail === 'string' ? resBody.detail : 'Failed to update skill';
    throw new ApiError(msg, res.status);
  }
  return res.json();
}

export async function deleteSkill(token: string, skillId: string): Promise<void> {
  const res = await fetch(`/api/skills/${skillId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const resBody = await res.json().catch(() => ({}));
    const msg = typeof resBody?.error === 'string' ? resBody.error : typeof resBody?.detail === 'string' ? resBody.detail : 'Failed to delete skill';
    throw new ApiError(msg, res.status);
  }
}

// --- Conversations (persistent chat history) ---------------------------------─

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: CitationItem[];
  followUpSuggestions?: string[];
  createdAt: string;
}

export interface ConversationItem {
  id: string;
  title: string;
  messages: ConversationMessage[];
  isPinned: boolean;
  pinnedMessageIds: string[];
  createdAt: string;
  updatedAt: string;
  workspaceId?: string;
}

export interface CitationItem {
  id: string;
  chunkId?: string;
  documentId: string;
  documentName: string;
  pageNumber?: number;
  chunkText: string;
  relevanceScore: number;
  chunkType?: string;
  bbox?: { x0: number; y0: number; x1: number; y1: number } | null;
}

const CONVERSATIONS_KEY = (wid?: string | null) => `conversations:${wid ?? 'all'}`;

export async function fetchConversations(
  token: string | null,
  workspaceId?: string | null
): Promise<ConversationItem[]> {
  if (!token) return [];
  const url = workspaceId
    ? `/api/conversations?workspaceId=${encodeURIComponent(workspaceId)}`
    : '/api/conversations';
  const res = await fetchWithDedup(
    url,
    { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' },
    CONVERSATIONS_KEY(workspaceId)
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = typeof body?.error === 'string' ? body.error : 'Failed to load conversations';
    throw new ApiError(msg, res.status);
  }
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function fetchConversation(
  token: string | null,
  conversationId: string
): Promise<ConversationItem> {
  if (!token) throw new ApiError('Authentication required', 401);
  const res = await fetch(`/api/conversations/${conversationId}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = typeof body?.error === 'string' ? body.error : 'Failed to load conversation';
    throw new ApiError(msg, res.status);
  }
  return res.json();
}

export async function createConversation(
  token: string,
  workspaceId?: string | null
): Promise<ConversationItem> {
  const res = await fetch('/api/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ workspaceId: workspaceId ?? null }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = typeof body?.error === 'string' ? body.error : 'Failed to create conversation';
    throw new ApiError(msg, res.status);
  }
  return res.json();
}

export async function updateConversation(
  token: string,
  conversationId: string,
  body: { title?: string; isPinned?: boolean; pinnedMessageIds?: string[] }
): Promise<ConversationItem> {
  const res = await fetch(`/api/conversations/${conversationId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const resBody = await res.json().catch(() => ({}));
    const msg = typeof resBody?.error === 'string' ? resBody.error : 'Failed to update conversation';
    throw new ApiError(msg, res.status);
  }
  return res.json();
}

export async function deleteConversation(
  token: string,
  conversationId: string
): Promise<void> {
  const res = await fetch(`/api/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = typeof body?.error === 'string' ? body.error : 'Failed to delete conversation';
    throw new ApiError(msg, res.status);
  }
}

export async function syncConversationMessages(
  token: string,
  conversationId: string,
  messages: ConversationMessage[]
): Promise<void> {
  // Sync messages by posting any that don't exist on backend
  for (const msg of messages) {
    try {
      await fetch(`/api/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          role: msg.role,
          content: msg.content,
          citations: msg.citations,
          followUpSuggestions: msg.followUpSuggestions,
        }),
      });
    } catch {
      // Non-fatal: message sync failed
    }
  }
}

/**
 * Generate a short, descriptive title from a conversation's messages.
 */
export async function generateConversationTitle(
  token: string,
  messages: ConversationMessage[]
): Promise<string> {
  const res = await fetch('/api/ai/generate-title', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ messages }),
  });
  if (!res.ok) throw new ApiError('Failed to generate title', res.status);
  const data = await res.json();
  return typeof data.title === 'string' ? data.title.trim() : '';
}



'use client';

import { useCallback, useRef } from 'react';
import { Citation } from '@/store/chatStore';

export type ChatStatus = 'searching' | 'thinking' | 'streaming' | 'complete' | 'error';

interface StreamCallbacks {
  onContent: (content: string) => void;
  onCitations: (citations: Citation[]) => void;
  onFollowUps: (suggestions: string[]) => void;
  onError: (message: string) => void;
  onDone: () => void;
  onStatus: (status: ChatStatus, message?: string) => void;
  scheduleFlush: (convId: string, messageId: string, force?: boolean) => void;
}

interface UseSSEStreamOptions {
  token: string | null;
}

export function useSSEStream({ token }: UseSSEStreamOptions) {
  const isStreamingRef = useRef(false);

  const resetStreamingState = useCallback(() => {
    // no-op - content state is owned by the caller via onContent + scheduleFlush
  }, []);

  const streamChat = useCallback(
    async (
      message: string,
      conversationId: string,
      assistantMessageId: string,
      workspaceId: string | null,
      documentIds: string[] | undefined,
      contextChunkId: string | undefined,
      skill: string | null,
      callbacks: StreamCallbacks
    ) => {
      resetStreamingState();
      isStreamingRef.current = true;

      const headers: HeadersInit = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: message.trim(),
          conversationId,
          workspaceId: workspaceId ?? undefined,
          documentIds: documentIds ?? undefined,
          contextChunkId: contextChunkId ?? undefined,
          skill: skill ?? undefined,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Server error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (!reader) {
        callbacks.onError('No response stream available');
        callbacks.onDone();
        return;
      }

      while (isStreamingRef.current) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;

              try {
              const parsed = JSON.parse(data);
              if (parsed.type === 'content') {
                callbacks.onContent(parsed.content);
                callbacks.scheduleFlush(conversationId, assistantMessageId);
              } else if (parsed.type === 'citations') {
                callbacks.onCitations(parsed.citations as Citation[]);
              } else if (parsed.type === 'follow_ups' && Array.isArray(parsed.suggestions)) {
                callbacks.onFollowUps(parsed.suggestions);
              } else if (parsed.type === 'error') {
                callbacks.onError(parsed.message || 'Server error during streaming');
              } else if (parsed.type === 'status') {
                callbacks.onStatus(parsed.status, parsed.message);
              }
            } catch (parseErr) {
              if (parseErr instanceof SyntaxError) {
              } else if (parseErr instanceof Error) {
                callbacks.onError(parseErr.message);
                continue;
              }
              if (data.trim()) {
                callbacks.onContent(data);
                callbacks.scheduleFlush(conversationId, assistantMessageId);
              }
            }
          }
        }
      }

      if (buffer.startsWith('data: ')) {
        const data = buffer.slice(6);
        if (data && data !== '[DONE]') {
          try {
            const parsed = JSON.parse(data);
            if (parsed.type === 'content') {
              callbacks.onContent(parsed.content);
            }
          } catch {
            // Ignore incomplete JSON
          }
        }
      }

      callbacks.scheduleFlush(conversationId, assistantMessageId, true);
      callbacks.onDone();
    },
    [token, resetStreamingState]
  );

  const abortStreaming = useCallback(() => {
    isStreamingRef.current = false;
    resetStreamingState();
  }, [resetStreamingState]);

  return {
    streamChat,
    abortStreaming,
    resetStreamingState,
  };
}

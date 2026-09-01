import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/server/backendProxy';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    return await proxyToBackend(
      request,
      '/chat/stream',
      {
        method: 'POST',
        body: JSON.stringify({
          message: body.message,
          conversationId: body.conversationId,
          workspaceId: body.workspaceId,
          documentIds: body.documentIds ?? undefined,
          contextChunkId: body.contextChunkId ?? undefined,
          skill: body.skill ?? undefined,
        }),
      },
      { stream: true }
    );
  } catch {
    return NextResponse.json({ error: 'Failed to connect to backend' }, { status: 500 });
  }
}

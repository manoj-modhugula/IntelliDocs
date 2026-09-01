import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/server/backendProxy';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const response = await proxyToBackend(request, '/workspaces/');
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json(
        { error: response.status === 401 ? 'Unauthorized' : data?.detail ?? 'Failed to load workspaces' },
        { status: response.status }
      );
    }
    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        Pragma: 'no-cache',
      },
    });
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await proxyToBackend(request, '/workspaces/', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json(
        { error: data?.detail ?? data?.error ?? 'Failed to create workspace' },
        { status: response.status }
      );
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: 'Failed to create workspace' }, { status: 500 });
  }
}

import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function alternateBackendUrl(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.hostname === 'localhost') {
      parsed.hostname = '127.0.0.1';
      return parsed.toString();
    }
    if (parsed.hostname === '127.0.0.1') {
      parsed.hostname = 'localhost';
      return parsed.toString();
    }
  } catch {
    /* ignore */
  }
  return url;
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const auth = request.headers.get('Authorization');
    const headers: HeadersInit = {};
    if (auth) headers['Authorization'] = auth;

    const url = `${BACKEND_URL.replace(/\/$/, '')}/documents/${params.id}/status`;
    let response: Response;
    try {
      response = await fetch(url, { headers, cache: 'no-store' });
    } catch (firstErr) {
      const alt = alternateBackendUrl(url);
      if (alt === url) throw firstErr;
      response = await fetch(alt, { headers, cache: 'no-store' });
    }

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: body?.detail ?? body?.error ?? 'Failed to check status' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        Pragma: 'no-cache',
      },
    });
  } catch (error) {
    console.error('Status check error:', error);
    return NextResponse.json(
      { error: 'Failed to check status' },
      { status: 500 }
    );
  }
}

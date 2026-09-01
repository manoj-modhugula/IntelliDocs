import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  if (!params.id) {
    return NextResponse.json({ error: 'Document id required' }, { status: 400 });
  }

  const auth = request.headers.get('Authorization');
  try {
    const response = await fetch(`${BACKEND_URL}/documents/${params.id}/file`, {
      method: 'GET',
      headers: auth ? { Authorization: auth } : {},
      cache: 'no-store',
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const message =
        typeof data?.detail === 'string'
          ? data.detail
          : typeof data?.error === 'string'
            ? data.error
            : 'Original file is not available';
      return NextResponse.json({ error: message }, { status: response.status });
    }

    return new NextResponse(response.body, {
      status: 200,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'application/octet-stream',
        'Content-Disposition':
          response.headers.get('Content-Disposition') || 'inline',
        'Cache-Control': 'private, max-age=3600',
      },
    });
  } catch (error) {
    console.error('Document file proxy error:', error);
    return NextResponse.json({ error: 'Failed to load document file' }, { status: 502 });
  }
}

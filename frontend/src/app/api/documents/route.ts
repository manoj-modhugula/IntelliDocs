import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Forward auth header from incoming request to backend */
function getAuthHeaders(request: NextRequest): HeadersInit {
  const auth = request.headers.get('Authorization');
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (auth) headers['Authorization'] = auth;
  return headers;
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const workspaceId = searchParams.get('workspaceId');
    const refresh = searchParams.get('refresh');
    const url = new URL(`${BACKEND_URL}/documents/`);
    if (workspaceId) url.searchParams.set('workspaceId', workspaceId);
    if (refresh === '1' || refresh === 'true') url.searchParams.set('refresh', 'true');

    const response = await fetch(url.toString(), {
      headers: getAuthHeaders(request),
      cache: 'no-store',
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: await response.text() || 'Failed to list documents' },
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
    console.error('Documents list error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch documents' },
      { status: 500 }
    );
  }
}

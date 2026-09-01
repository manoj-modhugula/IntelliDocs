import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getAuthHeaders(request: NextRequest): HeadersInit {
  const auth = request.headers.get('Authorization');
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (auth) headers['Authorization'] = auth;
  return headers;
}

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${BACKEND_URL}/skills/`, {
      headers: getAuthHeaders(request),
      cache: 'no-store',
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = response.status === 401 ? 'Authentication required' : (body?.detail ?? 'Failed to load skills');
      return NextResponse.json({ error: detail }, { status: response.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { error: 'Backend unreachable' },
      { status: 502 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/skills/`, {
      method: 'POST',
      headers: getAuthHeaders(request),
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    if (!response.ok) {
      const resBody = await response.json().catch(() => ({}));
      const detail = response.status === 401 ? 'Authentication required' : (resBody?.detail ?? 'Failed to create skill');
      return NextResponse.json({ error: detail }, { status: response.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { error: 'Failed to create skill' },
      { status: 500 }
    );
  }
}

import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getAuthHeaders(request: NextRequest): HeadersInit {
  const auth = request.headers.get('Authorization');
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (auth) headers['Authorization'] = auth;
  return headers;
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params;
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/skills/${id}`, {
      method: 'PATCH',
      headers: getAuthHeaders(request),
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    if (!response.ok) {
      const resBody = await response.json().catch(() => ({}));
      const detail = response.status === 401 ? 'Authentication required' : (resBody?.detail ?? 'Failed to update skill');
      return NextResponse.json({ error: detail }, { status: response.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { error: 'Failed to update skill' },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params;
    const response = await fetch(`${BACKEND_URL}/skills/${id}`, {
      method: 'DELETE',
      headers: getAuthHeaders(request),
    });
    if (!response.ok) {
      const resBody = await response.json().catch(() => ({}));
      const detail = response.status === 401 ? 'Authentication required' : (resBody?.detail ?? 'Failed to delete skill');
      return NextResponse.json({ error: detail }, { status: response.status });
    }
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json(
      { error: 'Failed to delete skill' },
      { status: 500 }
    );
  }
}

import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getAuthHeaders(request: NextRequest): HeadersInit {
  const auth = request.headers.get('Authorization');
  const headers: HeadersInit = {};
  if (auth) headers['Authorization'] = auth;
  return headers;
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  if (!params.id) {
    return NextResponse.json({ error: 'Document id required' }, { status: 400 });
  }

  try {
    const base = BACKEND_URL.replace(/\/$/, '');
    const response = await fetch(`${base}/documents/${params.id}`, {
      method: 'DELETE',
      headers: getAuthHeaders(request),
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Delete failed' },
        { status: response.status }
      );
    }

    const data = await response.json().catch(() => ({ status: 'deleted', id: params.id }));
    return NextResponse.json(data);
  } catch (error) {
    console.error('Delete error:', error);
    return NextResponse.json(
      { error: 'Failed to delete document' },
      { status: 500 }
    );
  }
}

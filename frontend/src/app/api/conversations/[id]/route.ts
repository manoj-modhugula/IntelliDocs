import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getAuthHeaders(request: NextRequest): HeadersInit {
  const auth = request.headers.get('Authorization');
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (auth) headers['Authorization'] = auth;
  return headers;
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const response = await fetch(`${BACKEND_URL}/conversations/${params.id}/`, {
    headers: getAuthHeaders(request),
  });
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const body = await request.json();
  const response = await fetch(`${BACKEND_URL}/conversations/${params.id}/`, {
    method: 'PATCH',
    headers: getAuthHeaders(request),
    body: JSON.stringify(body),
  });
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const response = await fetch(`${BACKEND_URL}/conversations/${params.id}/`, {
    method: 'DELETE',
    headers: getAuthHeaders(request),
  });
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

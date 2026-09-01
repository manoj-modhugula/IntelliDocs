import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getAuthHeaders(request: NextRequest): HeadersInit {
  const auth = request.headers.get('Authorization');
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (auth) headers['Authorization'] = auth;
  return headers;
}

async function forwardRequest(
  method: string,
  url: string,
  request: NextRequest,
  body?: unknown
) {
  const response = await fetch(`${BACKEND_URL}${url}`, {
    method,
    headers: getAuthHeaders(request),
    body: body ? JSON.stringify(body) : undefined,
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const workspaceId = searchParams.get('workspaceId');

  let url = '/conversations/';
  if (workspaceId) url += `?workspaceId=${encodeURIComponent(workspaceId)}`;

  return forwardRequest('GET', url, request);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  return forwardRequest('POST', '/conversations/', request, body);
}

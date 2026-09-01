import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

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

function mergeHeaders(request: NextRequest, extra?: HeadersInit, json = true): Headers {
  const headers = new Headers(extra);
  if (json && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const auth = request.headers.get('Authorization');
  if (auth && !headers.has('Authorization')) {
    headers.set('Authorization', auth);
  }
  return headers;
}

async function fetchBackend(url: string, init: RequestInit): Promise<Response> {
  const alt = alternateBackendUrl(url);
  try {
    return await fetch(url, init);
  } catch (firstErr) {
    if (alt !== url) {
      try {
        return await fetch(alt, init);
      } catch {
        throw firstErr;
      }
    }
    throw firstErr;
  }
}

export async function proxyToBackend(
  request: NextRequest,
  path: string,
  init: RequestInit = {},
  options: { json?: boolean; stream?: boolean } = {}
): Promise<Response> {
  const json = options.json !== false;
  const url = `${BACKEND_URL}${path.startsWith('/') ? path : `/${path}`}`;
  const headers = mergeHeaders(request, init.headers as HeadersInit | undefined, json);
  const response = await fetchBackend(url, {
    ...init,
    headers,
    cache: 'no-store',
  });

  if (options.stream) {
    if (!response.body) {
      return new Response(null, { status: 204 });
    }
    return new Response(response.body, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  }

  const text = await response.text();
  let data: unknown = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text || 'Backend error' };
  }
  return NextResponse.json(data, { status: response.status });
}

export async function proxyJsonOrError(
  request: NextRequest,
  path: string,
  init: RequestInit = {},
  fallbackStatus = 502
): Promise<NextResponse> {
  try {
    const res = await proxyToBackend(request, path, init);
    return res as NextResponse;
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: fallbackStatus });
  }
}

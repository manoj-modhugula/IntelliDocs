import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/server/backendProxy';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await proxyToBackend(request, '/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: body.email, password: body.password }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json(
        { detail: data.detail || 'Login failed' },
        { status: response.status }
      );
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { detail: 'Cannot connect to backend. Is it running on port 8000?' },
      { status: 500 }
    );
  }
}

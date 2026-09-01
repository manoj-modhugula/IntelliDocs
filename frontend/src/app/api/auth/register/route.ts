import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: body.email, password: body.password, name: body.name }),
    });
    let data: { detail?: string } = {};
    try {
      data = await response.json();
    } catch {
      data = { detail: response.status === 502 ? 'Backend unavailable' : 'Registration failed' };
    }
    if (!response.ok) {
      return Response.json(
        { detail: data.detail || 'Registration failed' },
        { status: response.status }
      );
    }
    return Response.json(data);
  } catch (error) {
    console.error('Register API error:', error);
    return Response.json(
      { detail: 'Cannot connect to backend. Is it running on port 8000?' },
      { status: 500 }
    );
  }
}

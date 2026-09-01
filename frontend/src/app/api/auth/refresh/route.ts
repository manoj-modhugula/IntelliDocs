import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const auth = request.headers.get('Authorization');
    const response = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(auth ? { Authorization: auth } : {}),
      },
    });
    const data = await response.json();
    if (!response.ok) {
      return Response.json(
        { detail: data.detail || 'Token refresh failed' },
        { status: response.status }
      );
    }
    return Response.json(data);
  } catch (error) {
    console.error('Refresh API error:', error);
    return Response.json(
      { detail: 'Failed to connect to backend' },
      { status: 500 }
    );
  }
}

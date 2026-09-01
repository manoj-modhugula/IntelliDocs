import { NextRequest } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  try {
    const auth = request.headers.get('Authorization');
    const response = await fetch(`${BACKEND_URL}/auth/me`, {
      headers: auth ? { Authorization: auth } : {},
      cache: 'no-store',
    });
    const data = await response.json();
    if (!response.ok) {
      return Response.json(
        { detail: data.detail || 'Unauthorized' },
        { status: response.status }
      );
    }
    return Response.json(data);
  } catch (error) {
    console.error('Me API error:', error);
    return Response.json(
      { detail: 'Failed to connect to backend' },
      { status: 500 }
    );
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const auth = request.headers.get('Authorization');
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/auth/me`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(auth ? { Authorization: auth } : {}),
      },
      body: JSON.stringify({ workspace_id: body.workspace_id ?? body.workspaceId }),
    });
    const data = await response.json();
    if (!response.ok) {
      return Response.json(
        { detail: data.detail || 'Update failed' },
        { status: response.status }
      );
    }
    return Response.json(data);
  } catch (error) {
    console.error('Update me API error:', error);
    return Response.json(
      { detail: 'Failed to connect to backend' },
      { status: 500 }
    );
  }
}

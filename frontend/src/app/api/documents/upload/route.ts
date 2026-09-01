import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/server/backendProxy';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const response = await proxyToBackend(
      request,
      '/documents/upload',
      { method: 'POST', body: formData },
      { json: false }
    );
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = data.detail || data.error || 'Upload failed';
      return NextResponse.json(
        { error: typeof error === 'string' ? error : JSON.stringify(error) },
        { status: response.status }
      );
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: 'Failed to upload document' }, { status: 500 });
  }
}

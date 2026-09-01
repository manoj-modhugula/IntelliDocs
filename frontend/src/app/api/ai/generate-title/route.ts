import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/server/backendProxy';

export async function POST(req: NextRequest) {
  try {
    const { messages } = await req.json();
    if (!Array.isArray(messages) || messages.length === 0) {
      return NextResponse.json({ title: '' });
    }
    const response = await proxyToBackend(req, '/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify({ messages }),
    });
    if (!response.ok) return NextResponse.json({ title: '' });
    const data = await response.json().catch(() => ({}));
    return NextResponse.json({ title: typeof data.title === 'string' ? data.title : '' });
  } catch {
    return NextResponse.json({ title: '' });
  }
}

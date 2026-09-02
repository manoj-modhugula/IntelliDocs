'use client';

import { FileText } from 'lucide-react';
import Link from 'next/link';
import { useAuthStore } from '@/store/authStore';
import { Button } from '@/components/ui/Button';

export default function HomePage() {
  const token = useAuthStore((s) => s.token);
  const authReady = useAuthStore((s) => s.hasHydrated);
  const isAuthenticated = authReady && Boolean(token);

  return (
    <div className="relative h-full overflow-y-auto">
      <div className="relative z-10 flex min-h-full items-center justify-center px-6 py-10">
        <div className="w-full max-w-4xl text-center">
          <h1 className="hero-title mx-auto max-w-4xl text-[2.4rem] sm:text-[3.4rem] md:text-[4.2rem] text-ink">
            Ask your documents.
          </h1>

          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/chat">
              <Button variant="primary">Open chat</Button>
            </Link>
            <Link href="/documents">
              <Button variant="secondary">
                Upload documents
                <FileText className="h-4 w-4" />
              </Button>
            </Link>
          </div>

          {authReady && !isAuthenticated && (
            <p className="mt-5 text-xs text-muted">
              <Link href="/login" className="text-accent">
                Sign in
              </Link>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

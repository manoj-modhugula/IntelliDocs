'use client';

import { FileText, Layers3, Quote } from 'lucide-react';
import Link from 'next/link';
import { useAuthStore } from '@/store/authStore';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

export default function HomePage() {
  const token = useAuthStore((s) => s.token);
  const authReady = useAuthStore((s) => s.hasHydrated);
  const isAuthenticated = authReady && Boolean(token);

  return (
    <div className="relative h-full overflow-y-auto">
      <div className="relative z-10 flex min-h-full items-center justify-center px-6 py-10">
        <div className="w-full max-w-4xl text-center">
          <span className="eyebrow">IntelliDocs</span>

          <h1 className="hero-title mx-auto mt-6 max-w-4xl text-[2.4rem] sm:text-[3.4rem] md:text-[4.2rem] text-ink">
            Ask your documents.
            <br />
            <span className="text-muted">Get cited answers.</span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-ink-soft sm:text-lg">
            Upload PDFs, Word files, and notes. Search them with hybrid retrieval and
            receive answers grounded in the source text, with page citations.
          </p>

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
              </Link>{' '}
              to save chats, workspaces, and uploads.
            </p>
          )}

          <div className="card-grid card-grid-3 mt-12 text-left">
            <Card>
              <Quote className="mb-3 h-4 w-4 text-ink-soft" />
              <p className="card-title">Cited answers</p>
              <p className="mt-1 text-sm leading-6 text-muted">
                Every response includes source passages and page numbers from your files.
              </p>
            </Card>
            <Card>
              <Layers3 className="mb-3 h-4 w-4 text-ink-soft" />
              <p className="card-title">Workspaces</p>
              <p className="mt-1 text-sm leading-6 text-muted">
                Search across all documents or restrict retrieval to a single workspace.
              </p>
            </Card>
            <Card>
              <FileText className="mb-3 h-4 w-4 text-ink-soft" />
              <p className="card-title">Streaming</p>
              <p className="mt-1 text-sm leading-6 text-muted">
                Answers stream as they are generated so you can start reading immediately.
              </p>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

'use client';

import { FileText, Layers3, Quote } from 'lucide-react';
import Link from 'next/link';
import { useAuthStore } from '@/store/authStore';

export default function HomePage() {
  const token = useAuthStore((s) => s.token);
  const authReady = useAuthStore((s) => s.hasHydrated);
  const isAuthenticated = authReady && Boolean(token);

  return (
    <div className="relative h-full overflow-hidden">
      <div className="relative z-10 flex h-full items-center justify-center px-6 py-10">
        <div className="w-full max-w-6xl">
          <div className="relative mx-auto max-w-4xl text-center">
            <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full px-4 py-2 glass-chip text-[11px] font-medium uppercase tracking-[0.24em] text-slate-600 dark:text-slate-300">
              IntelliDocs
            </div>

            <div className="glass-depth mx-auto max-w-4xl">
              <div className="glass mx-auto max-w-4xl rounded-[2rem] px-6 py-8 sm:px-10 sm:py-10 md:px-14 md:py-12">
                <h1 className="mx-auto max-w-4xl text-[2.4rem] font-semibold leading-[1.05] tracking-[-0.04em] text-slate-900 dark:text-white sm:text-[3.4rem] md:text-[4.2rem]">
                  Ask your documents.
                  <br />
                  <span className="text-slate-500 dark:text-slate-400">Get cited answers.</span>
                </h1>
              </div>
            </div>

            <p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-slate-600 dark:text-slate-300 sm:text-lg">
              Upload PDFs, Word files, and notes. Search them with hybrid retrieval and
              receive answers grounded in the source text, with page citations.
            </p>

            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link href="/chat">
                <button
                  type="button"
                  className="hero-btn glass-interactive inline-flex items-center gap-2 rounded-2xl glass px-6 py-3.5 text-sm font-medium text-slate-900 dark:text-white"
                >
                  Open chat
                </button>
              </Link>
              <Link href="/documents">
                <button
                  type="button"
                  className="hero-btn glass-interactive inline-flex items-center gap-2 rounded-2xl glass px-6 py-3.5 text-sm font-medium text-slate-700 dark:text-slate-200"
                >
                  Upload documents
                  <FileText className="h-4 w-4" />
                </button>
              </Link>
            </div>

            {authReady && !isAuthenticated && (
              <p className="mt-5 text-xs text-slate-500 dark:text-slate-500">
                <Link href="/login" className="transition-colors hover:text-sky-500 dark:hover:text-sky-400">
                  Sign in
                </Link>
                {' '}to save chats, workspaces, and uploads.
              </p>
            )}

            <div className="mt-12 grid gap-3 sm:grid-cols-3">
              <div className="glass-depth">
                <div className="glass-interactive rounded-2xl glass px-4 py-4 text-left">
                  <Quote className="mb-3 h-4 w-4 text-slate-700 dark:text-white/80" />
                  <p className="text-sm font-medium text-slate-900 dark:text-white">Cited answers</p>
                  <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
                    Every response includes source passages and page numbers from your files.
                  </p>
                </div>
              </div>
              <div className="glass-depth">
                <div className="glass-interactive rounded-2xl glass px-4 py-4 text-left">
                  <Layers3 className="mb-3 h-4 w-4 text-slate-700 dark:text-white/80" />
                  <p className="text-sm font-medium text-slate-900 dark:text-white">Workspaces</p>
                  <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
                    Search across all documents or restrict retrieval to a single workspace.
                  </p>
                </div>
              </div>
              <div className="glass-depth">
                <div className="glass-interactive rounded-2xl glass px-4 py-4 text-left">
                  <FileText className="mb-3 h-4 w-4 text-slate-700 dark:text-white/80" />
                  <p className="text-sm font-medium text-slate-900 dark:text-white">Streaming</p>
                  <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
                    Answers stream as they are generated so you can start reading immediately.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

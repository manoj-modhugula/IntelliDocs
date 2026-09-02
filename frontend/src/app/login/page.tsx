'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import Link from 'next/link';
import { ArrowLeft, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Field, Label } from '@/components/ui/Field';

export default function LoginPage() {
  const router = useRouter();
  const { login, isLoading, error, clearError } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    try {
      await login(email, password);
      ['/', '/chat', '/documents', '/workspaces', '/settings'].forEach((href) => router.prefetch(href));
      router.push('/chat');
    } catch {
      // Error is handled by the store
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="mb-6">
          <Link href="/" className="inline-flex items-center gap-2 text-muted hover:text-ink text-sm">
            <ArrowLeft className="w-4 h-4 shrink-0" />
            Back to app
          </Link>
        </div>

        <div className="text-center mb-8">
          <span className="logo-mark mx-auto !h-14 !w-14 mb-4">
            <Sparkles className="w-7 h-7" />
          </span>
          <h1 className="page-title mt-4">IntelliDocs</h1>
          <p className="text-muted mt-2">Sign in to your account</p>
        </div>

        <Card className="p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && <div className="alert alert-bad">{error}</div>}

            <div>
              <Label htmlFor="email">Email address</Label>
              <Field
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                autoComplete="email"
              />
            </div>

            <div>
              <Label htmlFor="password">Password</Label>
              <Field
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>

            <Button type="submit" variant="primary" block disabled={isLoading} aria-busy={isLoading}>
              {isLoading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-muted text-sm">
              Don&apos;t have an account?{' '}
              <Link href="/register" className="text-ink font-semibold">
                Create one
              </Link>
            </p>
          </div>

          <div className="mt-6 pt-6" style={{ borderTop: '1px solid var(--line)' }}>
            <p className="text-muted text-xs text-center">
              Continue without an account?{' '}
              <Link href="/chat" className="text-ink-soft">
                Browse as guest
              </Link>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}

'use client';

import { Component, ReactNode, ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw, Home, Copy, CheckCircle } from 'lucide-react';
import Link from 'next/link';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorId: string | null;
  copied: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null, errorId: null, copied: false };
  }

  static getDerivedStateFromError(error: Error): State {
    const errorId = `err-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
    return { hasError: true, error, errorInfo: null, errorId, copied: false };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught error:', error, errorInfo);
    this.setState({ errorInfo });

    if (typeof window !== 'undefined') {
      console.error('Error details:', {
        errorId: this.state.errorId,
        error: error.toString(),
        stack: errorInfo.componentStack,
        url: window.location.href,
      });
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null, errorId: null, copied: false });
    window.location.reload();
  };

  handleCopy = () => {
    const { error, errorId } = this.state;
    if (!error) return;
    const text = [`Error ID: ${errorId}`, `Error: ${error.toString()}`, `Stack: ${error.stack || 'no stack'}`, `URL: ${typeof window !== 'undefined' ? window.location.href : 'unknown'}`].join('\n');
    navigator.clipboard.writeText(text).then(() => {
      this.setState({ copied: true });
      setTimeout(() => this.setState({ copied: false }), 2000);
    });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const { error, errorInfo, errorId, copied } = this.state;

      return (
        <div className="min-h-screen flex items-center justify-center p-4" role="alert" aria-live="assertive">
          <div className="max-w-md w-full text-center">
            <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
              <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400" />
            </div>

            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-3">
              Something went wrong
            </h1>

            {errorId && (
              <div className="mb-4 inline-flex items-center gap-2 px-3 py-1.5 glass rounded-md text-sm text-slate-600 dark:text-slate-300 font-mono">
                <span>ID: {errorId}</span>
                <button
                  onClick={this.handleCopy}
                  className="p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded transition-colors"
                  aria-label="Copy error details"
                  title="Copy error details"
                >
                  {copied ? <CheckCircle className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            )}

            {process.env.NODE_ENV === 'development' && error && (
              <div className="mb-6 p-4 glass rounded-lg text-left overflow-auto max-h-48 text-left">
                <p className="text-sm font-mono text-red-600 dark:text-red-400 mb-2">
                  {error.toString()}
                </p>
                {errorInfo && (
                  <pre className="text-xs text-slate-600 dark:text-slate-400 whitespace-pre-wrap">
                    {errorInfo.componentStack}
                  </pre>
                )}
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={this.handleRetry}
                className="inline-flex items-center justify-center gap-2 px-6 py-3 glass text-sky-700 dark:text-sky-300 hover:bg-black/[0.05] dark:hover:bg-white/[0.08] rounded-lg font-medium transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </button>

              <Link
                href="/"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 glass text-slate-700 dark:text-slate-300 hover:bg-black/[0.05] dark:hover:bg-white/[0.08] rounded-lg font-medium transition-colors"
              >
                <Home className="w-4 h-4" />
                Go Home
              </Link>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export function useErrorHandler() {
  return (error: Error) => {
    console.error('Handled error:', error);
  };
}

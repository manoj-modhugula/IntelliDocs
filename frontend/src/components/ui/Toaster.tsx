'use client';

/**
 * Toast notification system with improved UX
 */
import { useEffect, useState, useCallback } from 'react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastOptions {
  duration?: number;
}

const toastListeners = new Set<(toast: Toast) => void>();

function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

export function toast(type: ToastType, message: string, options?: ToastOptions) {
  const toast: Toast = {
    id: generateId(),
    type,
    message,
    duration: options?.duration,
  };
  toastListeners.forEach(listener => listener(toast));
  return toast.id;
}

export function dismissToast(id: string) {
  toastListeners.forEach(listener => listener({ id, type: 'info', message: '', duration: 0 }));
}

const EXIT_MS = 300;

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [leavingIds, setLeavingIds] = useState<Set<string>>(new Set());

  const beginLeave = useCallback((id: string) => {
    setLeavingIds((prev) => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
      setLeavingIds((prev) => {
        if (!prev.has(id)) return prev;
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }, EXIT_MS);
  }, []);

  const addToast = useCallback((newToast: Toast) => {
    if (newToast.duration === 0) {
      beginLeave(newToast.id);
      return;
    }

    setToasts(prev => {
      // Check for duplicate
      if (prev.some(t => t.message === newToast.message && t.type === newToast.type)) {
        return prev;
      }
      return [...prev, newToast];
    });

    // Auto-dismiss
    const duration = newToast.duration ?? (newToast.type === 'error' ? 8000 : 4000);
    if (duration > 0) {
      setTimeout(() => {
        beginLeave(newToast.id);
      }, duration);
    }
  }, [beginLeave]);

  useEffect(() => {
    toastListeners.add(addToast);
    return () => {
      toastListeners.delete(addToast);
    };
  }, [addToast]);

  const getToastStyles = (type: ToastType) => {
    const base = 'alert flex items-center gap-3 pointer-events-auto';
    if (type === 'success') return `${base} alert-good`;
    if (type === 'error') return `${base} alert-bad`;
    if (type === 'warning') return `${base} alert-warn`;
    return `${base} alert-neutral`;
  };

  const getToastIcon = (type: ToastType) => {
    switch (type) {
      case 'success':
        return (
          <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        );
      case 'error':
        return (
          <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        );
      case 'warning':
        return (
          <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        );
      default:
        return (
          <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`${getToastStyles(toast.type)} pointer-events-auto max-w-sm min-w-[280px] ${
            leavingIds.has(toast.id)
              ? 'opacity-0 translate-y-[var(--enter-y)] transition-[opacity,transform] duration-leave ease-leave'
              : 'overlay-in'
          }`}
          style={leavingIds.has(toast.id) ? { animation: 'none' } : undefined}
          role="alert"
        >
          {getToastIcon(toast.type)}
          <p className="flex-1 text-sm font-medium">{toast.message}</p>
          <button
            onClick={() => dismissToast(toast.id)}
            className="p-1 rounded hover:bg-black/5 dark:hover:bg-white/8 transition-colors"
            aria-label="Dismiss"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}

export default toast;
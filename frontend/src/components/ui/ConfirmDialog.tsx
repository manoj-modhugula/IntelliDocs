'use client';

import { memo, useEffect, useRef, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

const EXIT_MS = 300;

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'default';
  onConfirm: () => void;
  onCancel: () => void;
}

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export const ConfirmDialog = memo(function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  variant = 'danger',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [shown, setShown] = useState(open);
  const titleRef = useRef(title);
  const messageRef = useRef(message);
  const confirmLabelRef = useRef(confirmLabel);
  const cancelLabelRef = useRef(cancelLabel);

  if (open) {
    titleRef.current = title;
    messageRef.current = message;
    confirmLabelRef.current = confirmLabel;
    cancelLabelRef.current = cancelLabel;
  }

  if (open && !shown) {
    setShown(true);
  }

  useEffect(() => {
    if (open || !shown) return;
    const id = window.setTimeout(() => setShown(false), EXIT_MS);
    return () => window.clearTimeout(id);
  }, [open, shown]);

  useEffect(() => {
    if (!open) return;
    const previousActive = document.activeElement as HTMLElement | null;
    cancelRef.current?.focus({ preventScroll: true });
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCancel();
        return;
      }
      if (e.key !== 'Tab' || !dialogRef.current) return;
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previousActive?.focus?.({ preventScroll: true });
    };
  }, [open, onCancel]);

  if (!shown) return null;

  return (
    <div
      role="dialog"
      aria-modal={open}
      aria-hidden={!open}
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-desc"
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center p-4',
        !open && 'pointer-events-none'
      )}
    >
      <div
        className={cn(
          'fixed inset-0 bg-[rgba(15,23,42,0.32)] backdrop-blur-sm overlay-backdrop',
          open ? 'opacity-100' : 'opacity-0'
        )}
        onClick={open ? onCancel : undefined}
        aria-hidden
      />
      <div
        ref={dialogRef}
        className={cn(
          'card relative w-full max-w-md p-6',
          open
            ? 'overlay-in'
            : 'opacity-0 translate-y-[var(--enter-y)] transition-[opacity,transform] duration-leave ease-leave'
        )}
        style={open ? undefined : { animation: 'none' }}
      >
        <div className="flex gap-4">
          <div
            className={cn(
              'flex h-10 w-10 shrink-0 items-center justify-center rounded-full',
              variant === 'danger' ? 'logo-mark icon-btn-danger !h-10 !w-10' : 'logo-mark'
            )}
          >
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 id="confirm-dialog-title" className="card-title text-lg">
              {titleRef.current}
            </h2>
            <p id="confirm-dialog-desc" className="mt-1 text-sm text-muted">
              {messageRef.current}
            </p>
            <div className="mt-4 flex gap-2">
              <button ref={cancelRef} type="button" onClick={onCancel} className="btn btn-secondary !py-2 !px-4 text-sm">
                {cancelLabelRef.current}
              </button>
              <button
                type="button"
                onClick={onConfirm}
                className={cn('btn !py-2 !px-4 text-sm', variant === 'danger' ? 'btn-danger' : 'btn-primary')}
              >
                {confirmLabelRef.current}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

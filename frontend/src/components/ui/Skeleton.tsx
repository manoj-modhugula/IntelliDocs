'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
}

export const Skeleton = memo(function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-lg bg-slate-200/60 dark:bg-slate-700/40',
        className
      )}
      aria-hidden="true"
    />
  );
});

export const ConversationSkeleton = memo(function ConversationSkeleton() {
  return (
    <div className="space-y-1 px-2 py-2" aria-label="Loading conversations">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-xl">
          <Skeleton className="h-4 w-4 rounded" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3 w-3/4 rounded" />
            <Skeleton className="h-2 w-1/2 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
});

export const DocumentSkeleton = memo(function DocumentSkeleton() {
  return (
    <div className="space-y-1 px-2 py-2" aria-label="Loading documents">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-xl">
          <Skeleton className="h-4 w-4 rounded" />
          <div className="flex-1 space-y-1">
            <Skeleton className="h-3 w-2/3 rounded" />
            <Skeleton className="h-2 w-1/3 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
});

export const ChatMessageSkeleton = memo(function ChatMessageSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-4 px-6 py-4" aria-label="Loading messages">
      {[...Array(count)].map((_, i) => (
        <div key={i} className={cn('flex gap-3', i % 2 === 0 ? 'flex-row' : 'flex-row-reverse')}>
          <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
          <div className="flex-1 space-y-2 max-w-lg">
            <Skeleton className="h-3 w-1/4 rounded" />
            <Skeleton className="h-4 w-full rounded" />
            <Skeleton className="h-4 w-5/6 rounded" />
            {i === 0 && <Skeleton className="h-4 w-3/4 rounded" />}
          </div>
        </div>
      ))}
    </div>
  );
});

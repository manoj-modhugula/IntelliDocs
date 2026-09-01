'use client';

import { memo } from 'react';
import { motion } from 'framer-motion';
import { Search, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatStatus } from '@/hooks/useSSEStream';

interface ChatStatusIndicatorProps {
  status: ChatStatus;
  message?: string;
  className?: string;
}

export const ChatStatusIndicator = memo(function ChatStatusIndicator({
  status,
  message,
  className,
}: ChatStatusIndicatorProps) {
  if (status === 'complete' || status === 'error') return null;

  return (
    <motion.div
      key={status}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.15 }}
      className={cn('flex items-center gap-2 px-4 py-2 text-sm text-slate-500 dark:text-slate-400', className)}
    >
      {status === 'searching' && (
        <>
          <Search className="w-4 h-4 animate-pulse" />
          <span>{message || 'Searching documents...'}</span>
        </>
      )}
      {status === 'thinking' && (
        <>
          <Sparkles className="w-4 h-4 animate-pulse" />
          <span>{message || 'Generating answer...'}</span>
        </>
      )}
      {status === 'streaming' && (
        <>
          <span className="w-2 h-2 rounded-full bg-sky-500 animate-pulse" />
          <span>Generating...</span>
        </>
      )}
    </motion.div>
  );
});

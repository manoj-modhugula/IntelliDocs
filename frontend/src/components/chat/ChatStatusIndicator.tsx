'use client';

import { memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatStatus } from '@/hooks/useSSEStream';

interface ChatStatusIndicatorProps {
  status: ChatStatus;
  message?: string;
  className?: string;
}

const SETTLE = { duration: 0.34, ease: [0.22, 1, 0.36, 1] as const };

export const ChatStatusIndicator = memo(function ChatStatusIndicator({
  status,
  message,
  className,
}: ChatStatusIndicatorProps) {
  const visible = status !== 'complete' && status !== 'error';

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key={status}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={SETTLE}
          className={cn('flex items-center gap-2 px-4 py-2 text-sm text-slate-500 dark:text-slate-400', className)}
        >
          {status === 'searching' && (
            <>
              <Search className="w-4 h-4 animate-pulse" />
              <span>{message || 'Searching'}</span>
            </>
          )}
          {status === 'thinking' && (
            <>
              <Sparkles className="w-4 h-4 animate-pulse" />
              <span>{message || 'Generating'}</span>
            </>
          )}
          {status === 'streaming' && (
            <>
              <span className="w-2 h-2 rounded-full bg-sky-500 animate-pulse" />
              <span>Generating</span>
            </>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
});

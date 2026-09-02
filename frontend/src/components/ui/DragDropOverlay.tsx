'use client';

import { memo, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DragDropOverlayProps {
  onFileDrop: (file: File) => void;
  disabled?: boolean;
}

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
};

const ACCEPTED_EXTENSIONS = Object.values(ACCEPTED_TYPES).flat();

export const DragDropOverlay = memo(function DragDropOverlay({
  onFileDrop,
  disabled,
}: DragDropOverlayProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFileDrop(acceptedFiles[0]);
      }
    },
    [onFileDrop]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    disabled,
    multiple: false,
    noClick: true,
    noKeyboard: true,
  });

  return (
    <div {...getRootProps()} className="pointer-events-none fixed inset-0 z-[80]">
      <input {...getInputProps()} />

      <AnimatePresence>
        {isDragActive && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.34 }}
            className="absolute inset-0 flex items-center justify-center"
          >
            {/* Backdrop */}
            <div className="absolute inset-0 bg-slate-900/40 dark:bg-black/50 backdrop-blur-sm" />

            {/* Drop card */}
            <motion.div
              initial={{ scale: 0.88, y: 16 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.92, y: 8 }}
              transition={{ type: 'spring', stiffness: 240, damping: 32 }}
              className={cn(
                'relative z-10 flex flex-col items-center gap-4 px-10 py-10 rounded-3xl glass border-2 shadow-2xl max-w-sm text-center',
                isDragReject
                  ? 'border-rose-400/60 dark:border-rose-500/60'
                  : 'border-sky-400/60 dark:border-sky-500/60'
              )}
            >
              <motion.div
                animate={{ y: [0, -8, 0] }}
                transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }}
              >
                {isDragReject ? (
                  <AlertCircle className="w-12 h-12 text-rose-500 dark:text-rose-400" strokeWidth={1.5} />
                ) : (
                  <Upload className="w-12 h-12 text-sky-500 dark:text-sky-400" strokeWidth={1.5} />
                )}
              </motion.div>

              {isDragReject ? (
                <>
                  <p className="text-base font-semibold text-rose-700 dark:text-rose-300">
                    Unsupported file type
                  </p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Please drop a PDF, Word, or text file.
                  </p>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-slate-400 dark:text-slate-500" />
                    <p className="text-base font-semibold text-slate-900 dark:text-white">
                      Drop to upload
                    </p>
                  </div>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    PDF, Word (.docx), TXT, or Markdown
                  </p>
                </>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});

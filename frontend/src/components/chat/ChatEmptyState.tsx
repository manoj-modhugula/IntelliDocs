'use client';

import { memo, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, FileText, ArrowRight, Upload } from 'lucide-react';
import Link from 'next/link';

interface ChatEmptyStateProps {
  readyDocumentsCount: number;
  documentNames?: string[];
  onSuggestionClick: (question: string) => void;
  onFocusInput: () => void;
}

const QUESTION_SETS = {
  resume: [
    'Summarize my work experience',
    'What skills stand out most?',
    'How many years of experience?',
    'What are the key achievements?',
  ],
  generic: [
    'Summarize the key points',
    'What are the main findings?',
    'Explain the methodology',
    'List important dates or numbers',
  ],
  legal: [
    'Summarize the key terms',
    'What are the main obligations?',
    'Are there any risks mentioned?',
    'What is the effective date?',
  ],
  financial: [
    'Summarize the financial summary',
    'What are the key metrics?',
    'Are there any red flags?',
    'What is the revenue trend?',
  ],
  technical: [
    'Explain the technical architecture',
    'What are the main components?',
    'How does the system work?',
    'What are the dependencies?',
  ],
};

function detectDocumentType(names: string[]): keyof typeof QUESTION_SETS {
  const joined = names.join(' ').toLowerCase();
  if (/\b(resume|cv|curriculum|jobb?|work history|experience|skills|education)\b/.test(joined)) return 'resume';
  if (/\b(agreement|contract|terms|privacy|policy|legal|clause|liability)\b/.test(joined)) return 'legal';
  if (/\b(financial|report|revenue|profit|income|balance|sheet|earnings|quarter)\b/.test(joined)) return 'financial';
  if (/\b(technical|api|architecture|spec|system|component|diagram|code)\b/.test(joined)) return 'technical';
  return 'generic';
}

export const ChatEmptyState = memo(function ChatEmptyState({
  readyDocumentsCount,
  documentNames = [],
  onSuggestionClick,
}: ChatEmptyStateProps) {
  const questionSet = useMemo(
    () => QUESTION_SETS[documentNames.length > 0 ? detectDocumentType(documentNames) : 'generic'],
    [documentNames]
  );

  return (
    <div className="h-full flex flex-col items-center justify-center px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 320, damping: 28 }}
        className="text-center max-w-2xl w-full"
      >
        <span className="logo-mark mx-auto mb-6 !h-16 !w-16">
          <Sparkles className="w-7 h-7" strokeWidth={1.5} />
        </span>
        <h2 className="page-title mb-2">Ask with context.</h2>
        <p className="text-muted text-sm sm:text-base mb-8 max-w-xl mx-auto leading-relaxed">
          {readyDocumentsCount > 0
            ? "Turn your documents into a live conversation with grounded answers and citations."
            : "Upload a document to start a cleaner, source-grounded conversation."}
        </p>

        {readyDocumentsCount > 0 ? (
          <>
            <div className="flex flex-wrap items-center justify-center gap-2 mb-7 text-xs text-muted">
              <span className="chip">{readyDocumentsCount} doc{readyDocumentsCount > 1 ? 's' : ''} ready</span>
              <span className="chip">/short</span>
            </div>
            <div className="card-grid w-full">
            {questionSet.map((question) => (
              <button
                key={question}
                type="button"
                onClick={() => onSuggestionClick(question)}
                className="card suggestion-btn text-left p-4 text-sm text-ink-soft flex items-center gap-2 group"
              >
                <span className="flex-1">{question}</span>
                <ArrowRight className="w-4 h-4 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-[opacity,transform] duration-150 shrink-0" />
              </button>
            ))}
            </div>
            <p className="mt-6 text-xs text-muted">
              More controls in <Link href="/settings" className="text-accent">Settings</Link>.
            </p>
          </>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <span className="logo-mark !h-16 !w-16">
              <Upload className="w-7 h-7" strokeWidth={1.5} />
            </span>
            <p className="text-muted text-sm">No documents yet</p>
            <Link href="/documents" className="btn btn-primary">
              <FileText className="w-4 h-4" />
              Upload documents
            </Link>
          </div>
        )}
      </motion.div>
    </div>
  );
});

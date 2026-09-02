'use client';

import { memo, useMemo } from 'react';
import { FileText, ArrowRight, Upload } from 'lucide-react';
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
      <div className="page-enter text-center max-w-2xl w-full">
        {readyDocumentsCount > 0 ? (
          <div className="card-grid w-full">
            {questionSet.map((question) => (
              <button
                key={question}
                type="button"
                onClick={() => onSuggestionClick(question)}
                className="card suggestion-btn text-left p-4 text-sm text-ink-soft flex items-center gap-2 group"
              >
                <span className="flex-1">{question}</span>
                <ArrowRight className="w-4 h-4 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-[opacity,transform] duration-hover ease-out shrink-0" />
              </button>
            ))}
          </div>
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
      </div>
    </div>
  );
});

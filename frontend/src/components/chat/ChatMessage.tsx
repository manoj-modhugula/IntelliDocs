'use client';

import { useState, memo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Sparkles, FileText, ChevronDown, ChevronUp, Copy, Check, Pin, PinOff, MessageCircle, BookOpen } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Message, Citation } from '@/store/chatStore';
import { cn } from '@/lib/utils';

export const DEFAULT_FOLLOW_UP_SUGGESTIONS = [
  'Explain more',
  'Give an example',
  'What are the limitations?',
];

interface ChatMessageProps {
  message: Message;
  isPinned?: boolean;
  onPin?: () => void;
  followUpSuggestions?: string[];
  onFollowUpClick?: (text: string) => void;
  onAskAboutChunk?: (citation: Citation) => void;
  onOpenSource?: (citation: Citation) => void;
}

const remarkPlugins = [remarkMath, remarkGfm];
const rehypePlugins = [rehypeKatex];

const BARE_MATH_INDICATOR =
  /\\(?:pmod|frac|gcd|equiv|leq|geq|neq|cdot|times|rightarrow|left|right|sum|int|alpha|beta|gamma|theta|infty|sin|cos|tan|log|ln|exp|sqrt|quad|qquad)\s*[{(]|\\^\\{|\\_\\{|\\b\\gcd\\s*\(/;

function wrapBareMathInSegment(segment: string): string {
  if (!segment || segment.includes('$')) return segment;
  let result = '';
  let remaining = segment;
  while (remaining.length > 0) {
    const match = remaining.match(BARE_MATH_INDICATOR);
    if (!match || match.index == null) {
      result += remaining;
      break;
    }
    const firstMathIdx = match.index;
    // Start of run: 0 or position right after last break (., !, ?, \n, or " where "/" and "/" with ") before firstMathIdx
    const before = remaining.slice(0, firstMathIdx);
    const breakStarts: number[] = [0, ...Array.from(before.matchAll(/[.!?\n]/g), (m) => (m.index ?? 0) + 1)];
    for (const w of [' where ', ' and ', ' with ']) {
      const i = before.lastIndexOf(w);
      if (i !== -1) breakStarts.push(i + w.length);
    }
    const runStart = Math.max(...breakStarts.filter((s) => s <= firstMathIdx), 0);

    // End of run: next " where "/" and "/" with " or .,;:!?\n or end
    const afterFirst = remaining.slice(firstMathIdx);
    const endMatch = afterFirst.match(/\s+(?:where|and|with)\s+|[.,;:!?\n]/);
    const runEndRel = endMatch ? endMatch.index ?? afterFirst.length : afterFirst.length;
    const runEnd = firstMathIdx + runEndRel;
    const run = remaining.slice(runStart, runEnd).trim();
    const afterRun = remaining.slice(runEnd);

    if (!run) {
      result += remaining.slice(0, runEnd);
      remaining = afterRun;
      continue;
    }
    result += remaining.slice(0, runStart) + `$${run}$`;
    remaining = afterRun;
  }
  return result;
}

/**
 * Normalize LaTeX delimiters so remark-math/rehype-katex render all math.
 * - Converts \( ... \) → $ ... $ and \[ ... \] → $$ ... $$
 * - Wraps bare \begin{...} display environments in $$ and normalizes \end{...} to match \begin{...}
 * - Wraps bare inline LaTeX (e.g. D(y) = a^{-1}(y - b) \pmod{30}) in $...$ when not already delimited.
 * Preserves existing $ / $$ and does not strip any symbols.
 */
function normalizeMathDelimiters(text: string): string {
  if (!text || typeof text !== 'string') return text;
  let out = text;

  out = out.replace(/\\\[([\s\S]*?)\\\]/g, '$$$1$$');

  out = out.replace(/\\\(([\s\S]*?)\\\)/g, (_m, g1) => `$${g1}$`);

  const openEnv = '(align\\*?|aligned|equation\\*?|gather\\*?|eqnarray\\*?|multline\\*?)';
  const closeEnv = '(align\\*?|aligned\\*?|equation\\*?|gather\\*?|eqnarray\\*?|multline\\*?)';
  const envPattern = new RegExp(
    `\\\\begin\\{${openEnv}\\}([\\s\\S]*?)\\\\end\\{${closeEnv}\\}`,
    'g'
  );
  out = out.replace(envPattern, (_full, openName, content) => `$$\\begin{${openName}}${content}\\end{${openName}}$$`);
  out = out.replace(/\$\$\$\$/g, '$$');

  const parts = out.split(/(\$\$|\$)/);
  for (let i = 0; i < parts.length; i += 4) {
    parts[i] = wrapBareMathInSegment(parts[i]);
  }
  out = parts.join('');

  out = out.replace(/\$\s*\$\$([\s\S]*?)\$\$\s*\$/g, '$$$1$$');

  out = out.replace(/\$\s*\$\$/g, '$$');
  out = out.replace(/\$\$\s*\$/g, '$$');

  return out;
}
type MarkdownNodeProps = { children?: React.ReactNode };
const markdownComponents: import('react-markdown').Components = {
  p: ({ children }: MarkdownNodeProps) => (
    <p className="mb-3 last:mb-0 leading-[1.75] text-slate-700 dark:text-slate-300">{children}</p>
  ),
  ul: ({ children }: MarkdownNodeProps) => (
    <ul className="list-disc pl-5 mb-3 space-y-1.5">{children}</ul>
  ),
  ol: ({ children }: MarkdownNodeProps) => (
    <ol className="list-decimal pl-5 mb-3 space-y-1.5">{children}</ol>
  ),
  li: ({ children }: MarkdownNodeProps) => (
    <li className="text-sm leading-relaxed text-slate-700 dark:text-slate-300 pl-1">{children}</li>
  ),
  h1: ({ children }: MarkdownNodeProps) => (
    <h1 className="text-xl font-bold mt-6 mb-3 text-slate-900 dark:text-slate-100 tracking-tight">{children}</h1>
  ),
  h2: ({ children }: MarkdownNodeProps) => (
    <h2 className="text-lg font-semibold mt-5 mb-2 text-slate-900 dark:text-slate-100 tracking-tight">{children}</h2>
  ),
  h3: ({ children }: MarkdownNodeProps) => (
    <h3 className="text-[0.9375rem] font-semibold mt-4 mb-1.5 text-slate-800 dark:text-slate-200">{children}</h3>
  ),
  h4: ({ children }: MarkdownNodeProps) => (
    <h4 className="text-sm font-semibold mt-3 mb-1 text-slate-700 dark:text-slate-300 uppercase tracking-wide">{children}</h4>
  ),
  hr: () => <hr className="my-5 border-slate-200 dark:border-slate-700" />,
  blockquote: ({ children }: MarkdownNodeProps) => (
    <blockquote className="border-l-[3px] border-indigo-300 dark:border-indigo-600 pl-4 pr-2 py-1 my-3 text-slate-600 dark:text-slate-400 card-bg rounded-r-lg">
      {children}
    </blockquote>
  ),
  table: ({ children }: MarkdownNodeProps) => (
    <div className="overflow-x-auto my-4 rounded-xl border border-white/20 dark:border-white/10 shadow-sm card-bg">
      <table className="min-w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }: MarkdownNodeProps) => (
    <thead className="card-bg">{children}</thead>
  ),
  tbody: ({ children }: MarkdownNodeProps) => <tbody className="divide-y divide-white/10 dark:divide-white/10">{children}</tbody>,
  tr: ({ children }: MarkdownNodeProps) => (
    <tr className="hover:opacity-90 transition-opacity">{children}</tr>
  ),
  th: ({ children }: MarkdownNodeProps) => (
    <th className="px-4 py-3 text-left font-semibold text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider border-b border-slate-200 dark:border-slate-700">
      {children}
    </th>
  ),
  td: ({ children }: MarkdownNodeProps) => (
    <td className="px-4 py-2.5 text-slate-700 dark:text-slate-300 leading-relaxed">{children}</td>
  ),
  code: ({ children, className }: MarkdownNodeProps & { className?: string }) => {
    const isBlock = className?.includes('language-');
    if (isBlock) {
      return (
        <pre className="bg-slate-900 dark:bg-slate-950 rounded-lg p-4 my-3 overflow-x-auto border border-slate-800 dark:border-slate-700 shadow-sm">
          <code className="text-[0.8125rem] leading-relaxed text-slate-100 font-mono">{children}</code>
        </pre>
      );
    }
    return (
      <code className="glass-chip text-indigo-700 dark:text-indigo-300 px-1.5 py-0.5 rounded text-[0.8125rem] font-mono border border-white/25 dark:border-white/10">
        {children}
      </code>
    );
  },
  strong: ({ children }: MarkdownNodeProps) => (
    <strong className="font-semibold text-slate-900 dark:text-slate-100">{children}</strong>
  ),
  em: ({ children }: MarkdownNodeProps) => (
    <em className="italic text-slate-600 dark:text-slate-400">{children}</em>
  ),
  a: ({ href, children }: MarkdownNodeProps & { href?: string }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-indigo-600 dark:text-indigo-400 underline underline-offset-2 decoration-indigo-300 dark:decoration-indigo-600 hover:text-indigo-800 dark:hover:text-indigo-300 hover:decoration-indigo-500 transition-colors"
    >
      {children}
    </a>
  ),
};

export const ChatMessage = memo(function ChatMessage({
  message,
  isPinned,
  onPin,
  followUpSuggestions,
  onFollowUpClick,
  onAskAboutChunk,
  onOpenSource,
}: ChatMessageProps) {
  const [showCitations, setShowCitations] = useState(false);
  const [copied, setCopied] = useState(false);

  const isUser = message.role === 'user';
  const hasCitations = message.citations && message.citations.length > 0;

  const copyToClipboard = useCallback(async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [message.content]);

  return (
    <div className={cn('flex gap-3 mb-4', isUser ? 'flex-row-reverse' : '')}>
      {/* Avatar - plain div with CSS transition, no JS motion overhead */}
      <div
        className="logo-mark !h-8 !w-8 flex-shrink-0"
      >
        {isUser ? (
          <User className="w-4 h-4" />
        ) : (
          <Sparkles className="w-4 h-4" />
        )}
      </div>

      <div className={cn('flex-1 min-w-0', isUser ? 'max-w-[80%] flex justify-end' : 'max-w-[90%]')}>
        {/* Message bubble - plain div, no Framer Motion */}
        <div
          className={cn(
            'card inline-block max-w-full overflow-hidden',
            isUser ? 'px-4 py-3' : 'px-5 py-4'
          )}
        >
          {message.isStreaming && !message.content ? (
            <TypingIndicator />
          ) : (
            <div className={cn('prose prose-sm max-w-none prose-slate dark:prose-invert break-words overflow-x-auto')}>
              <ReactMarkdown
                remarkPlugins={remarkPlugins}
                rehypePlugins={rehypePlugins}
                components={markdownComponents}
              >
                {normalizeMathDelimiters(message.content)}
              </ReactMarkdown>

              {message.isStreaming && message.content && (
                <span className="streaming-cursor" aria-hidden="true" />
              )}
            </div>
          )}
        </div>

        {/* Action bar - plain div with CSS transitions */}
        {!isUser && !message.isStreaming && message.content && (
          <div className="flex items-center gap-2 mt-2 ml-1 flex-wrap">
            {onPin && (
              <button
                type="button"
                onClick={onPin}
                className="action-btn flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-300"
                title={isPinned ? 'Unpin' : 'Pin to top'}
                aria-label={isPinned ? 'Unpin' : 'Pin to top'}
              >
                {isPinned ? (
                  <>
                    <PinOff className="w-3 h-3" />
                    <span>Unpin</span>
                  </>
                ) : (
                  <>
                    <Pin className="w-3 h-3" />
                    <span>Pin</span>
                  </>
                )}
              </button>
            )}
            <button
              type="button"
              onClick={copyToClipboard}
              aria-label={copied ? 'Copied to clipboard' : 'Copy response'}
              className="action-btn flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-300"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" aria-hidden />
                  <span className="text-emerald-700 dark:text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" aria-hidden />
                  <span>Copy</span>
                </>
              )}
            </button>
            <div aria-live="polite" aria-atomic="true" className="sr-only">
              {copied ? 'Copied to clipboard' : ''}
            </div>

            {hasCitations && (
              <button
                type="button"
                onClick={() => setShowCitations(!showCitations)}
                aria-expanded={showCitations}
                aria-controls="citations-panel"
                className="action-btn flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-300"
                title="Passages from your documents used to generate this answer"
              >
                <FileText className="w-3 h-3" />
                <span>{message.citations!.length} passage{message.citations!.length > 1 ? 's' : ''} cited</span>
                {showCitations ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
            )}
          </div>
        )}

        {/* Follow-up suggestions - plain CSS hover, no JS motion */}
        {!isUser && !message.isStreaming && message.content && onFollowUpClick && (() => {
          const suggestions = message.followUpSuggestions ?? followUpSuggestions;
          return suggestions && suggestions.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {suggestions.map((label) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => onFollowUpClick(label)}
                  className="suggestion-btn glass-interactive px-3 py-1.5 rounded-lg text-xs font-medium glass hover:bg-black/[0.07] dark:hover:bg-white/[0.1] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                >
                  {label}
                </button>
              ))}
            </div>
          ) : null;
        })()}

        {/* Citations - height spring + staggered cards */}
        <AnimatePresence initial={false}>
          {showCitations && hasCitations && (
            <motion.div
              key="citations-panel"
              id="citations-panel"
              className="mt-2 space-y-2 overflow-hidden"
              initial={{ opacity: 0, height: 0, y: -6 }}
              animate={{
                opacity: 1,
                height: 'auto',
                y: 0,
                transition: {
                  duration: 0.34,
                  ease: [0.22, 1, 0.36, 1],
                  staggerChildren: 0.04,
                  delayChildren: 0.02,
                },
              }}
              exit={{
                opacity: 0,
                height: 0,
                y: -6,
                transition: { duration: 0.3, ease: [0.4, 0, 1, 1] },
              }}
            >
              {message.citations!.map((citation, index) => (
                <motion.div
                  key={citation.id}
                  initial={{ opacity: 0, y: 8, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.98 }}
                  transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
                >
                  <CitationCard
                    citation={citation}
                    index={index + 1}
                    onAskAboutChunk={citation.chunkId && onAskAboutChunk ? () => onAskAboutChunk(citation) : undefined}
                    onOpenSource={onOpenSource ? () => onOpenSource(citation) : undefined}
                  />
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
});

// Typing indicator component
function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 bg-slate-400 dark:bg-slate-500 rounded-full animate-bounce"
          style={{ animationDelay: `${i * 0.15}s`, animationDuration: '0.6s' }}
        />
      ))}
    </div>
  );
}

// Citation card component
const CitationCard = memo(function CitationCard({
  citation,
  index,
  onAskAboutChunk,
  onOpenSource,
}: {
  citation: Citation;
  index: number;
  onAskAboutChunk?: () => void;
  onOpenSource?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={cn(
        'citation-card item-row p-3 cursor-pointer'
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start gap-2.5">
        <span className="flex-shrink-0 w-5 h-5 rounded-full glass text-slate-700 dark:text-slate-300 text-xs font-semibold flex items-center justify-center">
          {index}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="font-medium text-sm text-slate-900 dark:text-slate-100 truncate">
              {citation.documentName}
            </span>
            {citation.pageNumber && (
              <span className="text-xs text-slate-500 card-bg px-1.5 py-0.5 rounded border border-white/20 dark:border-white/10">p.{citation.pageNumber}</span>
            )}
          </div>
          <p className={cn(
            'text-xs text-slate-600 dark:text-slate-400 leading-relaxed',
            !expanded && 'line-clamp-2'
          )}>
            {citation.chunkText}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {onOpenSource && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenSource();
                }}
                className="action-btn flex items-center gap-1.5 text-xs text-amber-800 dark:text-amber-300 hover:text-amber-950 dark:hover:text-amber-200"
                title="Open this page in the source viewer"
              >
                <BookOpen className="w-3.5 h-3.5" />
                Open page
              </button>
            )}
            {onAskAboutChunk && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onAskAboutChunk();
                }}
                className="action-btn flex items-center gap-1.5 text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300"
                title="Ask a follow-up about this passage"
              >
                <MessageCircle className="w-3.5 h-3.5" />
                Ask about this
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

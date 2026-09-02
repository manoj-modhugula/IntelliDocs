'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { X, ChevronLeft, ChevronRight, FileText, Highlighter } from 'lucide-react';
import { fetchDocumentFile } from '@/lib/api';

export type SourceViewerBBox = {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
};

export type SourceViewerTarget = {
  documentId: string;
  documentName: string;
  fileType?: string;
  pageNumber?: number | null;
  chunkText: string;
  bbox?: SourceViewerBBox | null;
  chunkType?: string;
};

function isPdf(name: string, fileType?: string) {
  return (
    (fileType || '').includes('pdf') || name.toLowerCase().endsWith('.pdf')
  );
}

function isTextLike(name: string, fileType?: string) {
  const t = (fileType || '').toLowerCase();
  const n = name.toLowerCase();
  return (
    t.startsWith('text/') ||
    n.endsWith('.txt') ||
    n.endsWith('.md') ||
    n.endsWith('.markdown')
  );
}

function normalize(s: string) {
  return s.replace(/\s+/g, ' ').trim().toLowerCase();
}

function highlightHtml(text: string, excerpt: string): string {
  const needle = excerpt.replace(/\s+/g, ' ').trim();
  if (!needle) return text.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const idx = normalize(text).indexOf(normalize(needle).slice(0, 120));
  if (idx < 0) return escaped;
  const end = Math.min(text.length, idx + needle.length);
  return (
    escaped.slice(0, idx) +
    '<mark class="source-mark">' +
    escaped.slice(idx, end) +
    '</mark>' +
    escaped.slice(end)
  );
}

export function SourceViewer({
  target,
  token,
  onClose,
}: {
  target: SourceViewerTarget;
  token: string | null;
  onClose: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(Math.max(1, target.pageNumber || 1));
  const [pageCount, setPageCount] = useState(1);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [kind, setKind] = useState<'pdf' | 'text' | 'other'>('other');
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const pdfDocRef = useRef<{ numPages: number; getPage: (n: number) => Promise<unknown> } | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const excerpt = target.chunkText.replace(/\s+/g, ' ').trim();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const renderPdfPage = useCallback(
    async (pageNumber: number) => {
      const pdf = pdfDocRef.current;
      const canvas = canvasRef.current;
      const overlay = overlayRef.current;
      if (!pdf || !canvas || !overlay) return;
      const pdfPage = (await pdf.getPage(pageNumber)) as {
        getViewport: (opts: { scale: number }) => { width: number; height: number };
        render: (opts: object) => { promise: Promise<void> };
        getTextContent: () => Promise<{ items: Array<{ str?: string; transform?: number[] }> }>;
      };
      const containerWidth = canvas.parentElement?.clientWidth || 640;
      const unscaled = pdfPage.getViewport({ scale: 1 });
      const scale = Math.min(1.6, Math.max(0.9, containerWidth / unscaled.width));
      const viewport = pdfPage.getViewport({ scale });
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      overlay.width = viewport.width;
      overlay.height = viewport.height;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      await pdfPage.render({ canvasContext: ctx, viewport }).promise;

      const overlayCtx = overlay.getContext('2d');
      if (!overlayCtx) return;
      overlayCtx.clearRect(0, 0, overlay.width, overlay.height);
      overlayCtx.fillStyle = 'rgba(245, 215, 110, 0.4)';
      const bbox = target.bbox;
      if (bbox && [bbox.x0, bbox.y0, bbox.x1, bbox.y1].every((n) => typeof n === 'number')) {
        const vp = viewport as {
          convertToViewportRectangle?: (r: number[]) => number[];
          height: number;
          width: number;
        };
        let x = 0;
        let y = 0;
        let w = 0;
        let h = 0;
        if (typeof vp.convertToViewportRectangle === 'function') {
          const rect = vp.convertToViewportRectangle([bbox.x0, bbox.y0, bbox.x1, bbox.y1]);
          x = Math.min(rect[0], rect[2]);
          y = Math.min(rect[1], rect[3]);
          w = Math.abs(rect[2] - rect[0]);
          h = Math.abs(rect[3] - rect[1]);
        } else {
          x = bbox.x0 * scale;
          y = viewport.height - bbox.y1 * scale;
          w = (bbox.x1 - bbox.x0) * scale;
          h = (bbox.y1 - bbox.y0) * scale;
        }
        overlayCtx.fillRect(x - 2, y - 2, Math.max(w, 8) + 4, Math.max(h, 8) + 4);
        return;
      }
      const needle = normalize(excerpt).slice(0, 80);
      if (!needle) return;
      const content = await pdfPage.getTextContent();
      let joined = '';
      const spans: { start: number; end: number; x: number; y: number; w: number; h: number }[] = [];
      for (const item of content.items) {
        const str = item.str || '';
        const tr = item.transform || [1, 0, 0, 1, 0, 0];
        const fontHeight = Math.abs(tr[3] || 10) * scale;
        const x = tr[4] * scale;
        const y = viewport.height - tr[5] * scale - fontHeight;
        const w = Math.max(str.length * fontHeight * 0.45, 4);
        const start = joined.length;
        joined += str + ' ';
        spans.push({ start, end: joined.length, x, y, w, h: fontHeight + 4 });
      }
      const hay = normalize(joined);
      const at = hay.indexOf(needle);
      if (at < 0) return;
      for (const span of spans) {
        if (span.end < at || span.start > at + needle.length) continue;
        overlayCtx.fillRect(span.x - 1, span.y - 1, span.w + 2, span.h);
      }
    },
    [excerpt, target.bbox]
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setTextContent(null);
    pdfDocRef.current = null;

    (async () => {
      try {
        const { blob, contentType } = await fetchDocumentFile(token, target.documentId);
        if (cancelled) return;
        if (isPdf(target.documentName, target.fileType || contentType)) {
          setKind('pdf');
          const pdfjs = await import('pdfjs-dist');
          pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
          const data = await blob.arrayBuffer();
          const doc = await pdfjs.getDocument({ data }).promise;
          if (cancelled) {
            doc.destroy();
            return;
          }
          pdfDocRef.current = doc;
          setPageCount(doc.numPages);
          const startPage = Math.min(Math.max(1, target.pageNumber || 1), doc.numPages);
          setPage(startPage);
        } else if (isTextLike(target.documentName, target.fileType || contentType)) {
          setKind('text');
          setTextContent(await blob.text());
        } else {
          setKind('other');
          if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
          objectUrlRef.current = URL.createObjectURL(blob);
          setDownloadUrl(objectUrlRef.current);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Could not open this source');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [target.documentId, target.documentName, target.fileType, target.pageNumber, token]);

  useEffect(() => {
    if (kind === 'pdf' && pdfDocRef.current && !loading) {
      renderPdfPage(page).catch(() => setError('Could not render this page'));
    }
  }, [kind, page, loading, renderPdfPage]);

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-labelledby="source-viewer-title"
    >
      <button
        type="button"
        className="absolute inset-0 bg-[rgba(15,23,42,0.38)]"
        aria-label="Close source"
        onClick={onClose}
      />
      <aside className="relative flex h-full w-full max-w-xl flex-col sidebar-chrome rounded-none">
        <header className="flex items-start gap-3 px-4 py-3">
          <FileText className="mt-0.5 h-4 w-4 flex-shrink-0 text-ink-soft" />
          <div className="min-w-0 flex-1">
            <p id="source-viewer-title" className="truncate text-sm font-semibold text-ink">
              {target.documentName}
            </p>
            <p className="mt-0.5 flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] text-muted">
              <Highlighter className="h-3 w-3" />
              {target.pageNumber ? `Page ${target.pageNumber}` : 'Source passage'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="icon-btn !h-9 !w-9"
            aria-label="Close source viewer"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="relative min-h-0 flex-1 overflow-auto px-3 py-4">
          {loading && (
            <p className="px-2 text-sm text-slate-600 dark:text-amber-100/70">Opening source…</p>
          )}
          {error && (
            <p className="px-2 text-sm text-rose-700 dark:text-rose-300">{error}</p>
          )}
          {!loading && !error && kind === 'pdf' && (
            <div className="relative mx-auto w-fit shadow-[0_12px_40px_rgba(40,30,10,0.18)] ring-1 ring-black/10">
              <canvas ref={canvasRef} className="block bg-white" />
              <canvas
                ref={overlayRef}
                className="pointer-events-none absolute inset-0"
                data-testid="source-overlay"
                data-highlight={target.bbox ? 'geometry' : 'text'}
                aria-hidden
              />
            </div>
          )}
          {!loading && !error && kind === 'text' && textContent !== null && (
            <pre
              className="source-paper whitespace-pre-wrap break-words rounded-sm bg-[#fffdf7] p-4 text-[13px] leading-6 text-slate-800 shadow-inner ring-1 ring-amber-900/10"
              dangerouslySetInnerHTML={{ __html: highlightHtml(textContent, excerpt) }}
            />
          )}
          {!loading && !error && kind === 'other' && downloadUrl && (
            <p className="px-2 text-sm text-slate-700 dark:text-amber-100/80">
              This file type cannot be previewed here.{' '}
              <a
                href={downloadUrl}
                download={target.documentName}
                className="underline underline-offset-2"
              >
                Download {target.documentName}
              </a>
            </p>
          )}
        </div>

        {kind === 'pdf' && pageCount > 1 && (
          <div className="flex items-center justify-center gap-3 border-t border-black/10 px-4 py-2 dark:border-white/10">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded-lg p-1.5 disabled:opacity-30"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-xs tabular-nums text-slate-700 dark:text-amber-100">
              {page} / {pageCount}
            </span>
            <button
              type="button"
              disabled={page >= pageCount}
              onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
              className="rounded-lg p-1.5 disabled:opacity-30"
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {excerpt && (
          <blockquote className="border-t border-black/10 px-4 py-3 text-xs leading-5 text-slate-700 dark:border-white/10 dark:text-amber-100/80">
            <span className="mr-1 font-medium text-amber-800 dark:text-amber-200">Cited</span>
            {excerpt.slice(0, 280)}
            {excerpt.length > 280 ? '…' : ''}
          </blockquote>
        )}
      </aside>
    </div>
  );
}

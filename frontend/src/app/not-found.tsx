import Link from 'next/link';
import { Home, FileQuestion } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="h-full flex items-center justify-center bg-slate-50 dark:bg-slate-900 p-4">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 mx-auto mb-6 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
          <FileQuestion className="w-8 h-8 text-slate-500 dark:text-slate-400" />
        </div>
        <h2 className="text-xl font-semibold mb-2 text-slate-900 dark:text-slate-100">Page Not Found</h2>
        <p className="text-slate-600 dark:text-slate-400 mb-6 text-sm">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-4 py-2 bg-sky-200 dark:bg-sky-900/50 text-slate-900 dark:text-slate-100 rounded-lg hover:bg-sky-300 dark:hover:bg-sky-900/70 transition-colors"
        >
          <Home className="w-4 h-4" />
          Back to Home
        </Link>
      </div>
    </div>
  );
}

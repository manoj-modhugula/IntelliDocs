export default function Loading() {
  return (
    <div className="h-full flex items-center justify-center bg-slate-50 dark:bg-slate-900" role="status" aria-live="polite" aria-label="Loading">
      <div className="w-5 h-5 border-2 border-slate-300 dark:border-slate-600 border-t-sky-500 dark:border-t-sky-400 rounded-full animate-spin" aria-hidden />
    </div>
  );
}

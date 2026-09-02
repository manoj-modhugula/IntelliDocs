import type { LucideIcon } from 'lucide-react';

export function PageHeader({
  title,
  subtitle,
  action,
  icon: Icon,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2.5">
          {Icon && (
            <span className="logo-mark !h-10 !w-10">
              <Icon size={18} strokeWidth={2} aria-hidden />
            </span>
          )}
          <h1 className="page-title">{title}</h1>
        </div>
        {subtitle && <p className="mt-1.5 text-[0.95rem] leading-snug text-muted">{subtitle}</p>}
      </div>
      {action && <div className="flex shrink-0 items-center gap-1.5">{action}</div>}
    </div>
  );
}

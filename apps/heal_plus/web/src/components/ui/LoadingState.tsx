import { Loader2 } from 'lucide-react';

interface LoadingStateProps {
  label?: string;
  variant?: 'spinner' | 'skeleton';
  rows?: number;
}

export function LoadingState({ label = 'Carregando...', variant = 'spinner', rows = 4 }: LoadingStateProps) {
  if (variant === 'skeleton') {
    return (
      <div aria-busy="true" aria-live="polite" className="space-y-4 p-1 motion-safe:animate-fade-in" role="status">
        <span className="sr-only">{label}</span>
        {Array.from({ length: rows }).map((_, i) => (
            <div aria-hidden="true" key={i} className="flex gap-4 items-center">
            <div className="skeleton h-12 w-12 rounded-xl shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="skeleton h-4 w-3/4 rounded" />
              <div className="skeleton h-3 w-1/2 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div aria-busy="true" aria-live="polite" className="flex min-h-[240px] flex-col items-center justify-center gap-4 py-20 motion-safe:animate-fade-in" role="status">
      <div className="relative">
        <div aria-hidden="true" className="absolute inset-0 rounded-full bg-heal-blue/10 motion-safe:animate-ping" />
        <div className="relative flex h-12 w-12 items-center justify-center rounded-full bg-heal-softBlue dark:bg-blue-950/30">
          <Loader2 aria-hidden="true" className="h-6 w-6 text-heal-blue motion-safe:animate-spin" />
        </div>
      </div>
      <p className="text-sm font-medium text-heal-muted">{label}</p>
    </div>
  );
}

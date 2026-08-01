import { ArrowLeft, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { ReactNode } from 'react';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  showBack?: boolean;
  onBack?: () => void;
  showSidebarToggle?: boolean;
  isSidebarCollapsed?: boolean;
  onToggleSidebar?: () => void;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
  showBack,
  onBack,
  showSidebarToggle,
  isSidebarCollapsed,
  onToggleSidebar
}: PageHeaderProps) {
  const navigate = useNavigate();

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      navigate(-1);
    }
  };

  return (
    <header className="sticky top-0 z-30 bg-white/95 dark:bg-[#0c0c0e]/95 backdrop-blur-md border-b border-heal-line/60 dark:border-zinc-800/60 px-4 py-3 flex items-center justify-between gap-4 select-none">
      <div className="flex items-center gap-3.5 min-w-0 flex-1">
        {showSidebarToggle && onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-xl transition-all text-slate-600 dark:text-zinc-300 hover:text-slate-900 dark:hover:text-white cursor-pointer"
            title={isSidebarCollapsed ? "Mostrar barra lateral" : "Ocultar barra lateral"}
            type="button"
          >
            {isSidebarCollapsed ? (
              <PanelLeftOpen className="h-5 w-5 text-slate-600 dark:text-zinc-300" />
            ) : (
              <PanelLeftClose className="h-5 w-5 text-slate-600 dark:text-zinc-300" />
            )}
          </button>
        )}
        {showBack && (
          <button
            onClick={handleBack}
            className="p-2 hover:bg-slate-50 dark:hover:bg-zinc-900 rounded-full transition-colors text-heal-ink dark:text-white cursor-pointer"
            title="Voltar"
            type="button"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
        )}
        <div className="min-w-0 flex-1">
          {eyebrow && (
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-heal-blue mb-0.5">
              {eyebrow}
            </p>
          )}
          <h1 className="text-lg font-black text-heal-ink dark:text-white truncate leading-tight">
            {title}
          </h1>
          {description && (
            <p className="text-xs text-heal-muted dark:text-zinc-400 truncate mt-0.5 font-medium">
              {description}
            </p>
          )}
        </div>
      </div>

      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}

import { PanelLeftClose, PanelLeftOpen, History, ChevronDown, Plus } from 'lucide-react';
import { AiProviderMark } from '../AiProviderMark';
import type { AiProviderConfig } from '../aiProvider';
import { getAiProviderDefinition } from '../aiProvider';

interface ChatHeaderProps {
  isSidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  onOpenHistory: () => void;
  providerConfig: AiProviderConfig;
  onOpenProviderDialog: () => void;
  onNewChat: () => void;
}

export function ChatHeader({
  isSidebarCollapsed,
  onToggleSidebar,
  onOpenHistory,
  providerConfig,
  onOpenProviderDialog,
  onNewChat
}: ChatHeaderProps) {
  const activeProvider = getAiProviderDefinition(providerConfig.provider);
  const activeModelLabel =
    activeProvider.models.find((model) => model.id === providerConfig.model)?.label ??
    providerConfig.model ??
    activeProvider.label;

  return (
    <header className="z-20 flex h-12 shrink-0 items-center justify-between border-b border-slate-200 bg-white/95 px-3 backdrop-blur-md dark:border-zinc-900 dark:bg-[#0d0d0f]/95">
      <div className="flex min-w-0 items-center gap-1">
        <button
          aria-label={isSidebarCollapsed ? 'Mostrar navegação' : 'Ocultar navegação'}
          className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white transition-colors"
          onClick={onToggleSidebar}
          type="button"
        >
          {isSidebarCollapsed ? (
            <PanelLeftOpen className="h-4 w-4 text-slate-600 dark:text-zinc-300" />
          ) : (
            <PanelLeftClose className="h-4 w-4 text-slate-600 dark:text-zinc-300" />
          )}
        </button>

        <button
          aria-label="Abrir histórico"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white transition-colors"
          onClick={onOpenHistory}
          type="button"
        >
          <History className="h-4 w-4 text-slate-600 dark:text-zinc-300" />
        </button>

        <button
          aria-label={`Selecionar IA: ${activeModelLabel}`}
          className="flex h-9 min-w-0 max-w-[320px] items-center gap-2 rounded-lg px-2.5 text-left text-sm font-bold text-slate-900 hover:bg-slate-100 dark:text-white dark:hover:bg-zinc-800 transition-colors"
          onClick={onOpenProviderDialog}
          type="button"
        >
          <AiProviderMark provider={activeProvider.id} size="sm" />
          <span className="truncate">{activeModelLabel}</span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400 dark:text-zinc-500" />
        </button>
      </div>

      <button
        aria-label="Nova conversa"
        className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white transition-colors"
        onClick={onNewChat}
        type="button"
      >
        <Plus className="h-4 w-4 text-slate-600 dark:text-zinc-300" />
      </button>
    </header>
  );
}

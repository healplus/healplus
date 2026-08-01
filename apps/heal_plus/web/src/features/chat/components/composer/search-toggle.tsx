import { Database, Globe } from 'lucide-react';

interface SearchToggleProps {
  internalSearchEnabled: boolean;
  externalSearchEnabled: boolean;
  onToggleInternal: () => void;
  onToggleExternal: () => void;
}

export function SearchToggle({
  internalSearchEnabled,
  externalSearchEnabled,
  onToggleInternal,
  onToggleExternal
}: SearchToggleProps) {
  return (
    <div className="flex items-center gap-1 rounded-xl bg-slate-100/90 p-0.5 dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800">
      <button
        type="button"
        onClick={onToggleInternal}
        className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold transition-all ${
          internalSearchEnabled
            ? 'bg-white text-blue-700 shadow-sm dark:bg-slate-800 dark:text-blue-300'
            : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
        }`}
        title="Buscar prontuários e consultas no Heal+"
      >
        <Database size={13} className={internalSearchEnabled ? 'text-blue-600 dark:text-blue-400' : ''} />
        <span className="hidden sm:inline">Heal+</span>
      </button>

      <button
        type="button"
        onClick={onToggleExternal}
        className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold transition-all ${
          externalSearchEnabled
            ? 'bg-white text-blue-700 shadow-sm dark:bg-slate-800 dark:text-blue-300'
            : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
        }`}
        title="Pesquisar fontes médicas públicas (anonimizado)"
      >
        <Globe size={13} className={externalSearchEnabled ? 'text-blue-600 dark:text-blue-400' : ''} />
        <span className="hidden sm:inline">Web</span>
      </button>
    </div>
  );
}
